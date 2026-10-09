import json
import logging
import time
from pathlib import Path
from typing import List, Optional, Union
from contextlib import contextmanager

import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM

from ai.config import ai_config, get_device, get_torch_dtype
from ai.models.base import BaseMultimodalModel
from ai.schemas.analysis import DisasterAnalysis

logger = logging.getLogger(__name__)


class QwenVLModel(BaseMultimodalModel):
    """Qwen2.5-VL implementation for multimodal disaster analysis."""

    def __init__(self):
        self._model = None
        self._processor = None
        self._device = get_device()
        self._dtype = get_torch_dtype()
        self._loaded = False

    @property
    def model_name(self) -> str:
        return ai_config.AI_MODEL_NAME

    def is_loaded(self) -> bool:
        return self._loaded and self._model is not None

    def load(self) -> None:
        if self.is_loaded():
            logger.info(f"Model {self.model_name} already loaded")
            return

        logger.info(f"Loading model {self.model_name} on {self._device} with {self._dtype}")

        try:
            self._processor = AutoProcessor.from_pretrained(
                ai_config.AI_MODEL_NAME,
                revision=ai_config.AI_MODEL_REVISION,
                trust_remote_code=True,
            )

            model_kwargs = {
                "torch_dtype": self._dtype,
                "device_map": "auto" if self._device == "cuda" else None,
                "trust_remote_code": True,
            }

            if ai_config.AI_MAX_MEMORY and self._device == "cuda":
                model_kwargs["max_memory"] = {0: ai_config.AI_MAX_MEMORY}

            if ai_config.AI_OFFLOAD_FOLDER:
                model_kwargs["offload_folder"] = ai_config.AI_OFFLOAD_FOLDER

            self._model = AutoModelForCausalLM.from_pretrained(
                ai_config.AI_MODEL_NAME,
                revision=ai_config.AI_MODEL_REVISION,
                **model_kwargs,
            )

            if self._device != "cuda":
                self._model = self._model.to(self._device)

            self._model.eval()
            self._loaded = True
            logger.info(f"Model {self.model_name} loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            self._loaded = False
            raise

    def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
        if self._processor is not None:
            del self._processor
            self._processor = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self._loaded = False
        logger.info(f"Model {self.model_name} unloaded")

    def _prepare_messages_text(self, prompt: str, text: str) -> list:
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt.format(text=text)},
                ],
            }
        ]

    def _prepare_messages_image(self, prompt: str, image_path: Union[str, Path]) -> list:
        image = Image.open(image_path)
        if max(image.size) > ai_config.MAX_IMAGE_SIZE:
            image.thumbnail((ai_config.MAX_IMAGE_SIZE, ai_config.MAX_IMAGE_SIZE))

        return [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

    def _prepare_messages_frames(self, prompt: str, frame_paths: List[Union[str, Path]]) -> list:
        content = []
        for frame_path in frame_paths:
            image = Image.open(frame_path)
            if max(image.size) > ai_config.MAX_IMAGE_SIZE:
                image.thumbnail((ai_config.MAX_IMAGE_SIZE, ai_config.MAX_IMAGE_SIZE))
            content.append({"type": "image", "image": image})

        content.append({"type": "text", "text": prompt})

        return [
            {
                "role": "user",
                "content": content,
            }
        ]

    def _generate(self, messages: list) -> str:
        """Generate response from model."""
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load() first.")

        text = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self._processor(
            text=[text],
            images=[msg["content"] for msg in messages if any(c.get("type") == "image" for c in msg["content"])],
            padding=True,
            return_tensors="pt",
        ).to(self._device)

        with torch.no_grad():
            generated_ids = self._model.generate(
                **inputs,
                max_new_tokens=ai_config.AI_MAX_NEW_TOKENS,
                temperature=ai_config.AI_TEMPERATURE,
                top_p=ai_config.AI_TOP_P,
                do_sample=ai_config.AI_DO_SAMPLE,
                pad_token_id=self._processor.tokenizer.eos_token_id,
            )

        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]

        response = self._processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]

        return response.strip()

    def _parse_response(self, response: str) -> DisasterAnalysis:
        """Parse model response into DisasterAnalysis."""
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response.strip())
            return DisasterAnalysis(**data)

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse model response as JSON: {e}")
            logger.debug(f"Raw response: {response[:500]}")
            return DisasterAnalysis(
                summary="Failed to parse structured output from model",
                evidence_description=f"Raw model response: {response[:200]}",
            )

    def analyze_text(self, text: str, prompt: str) -> DisasterAnalysis:
        start_time = time.time()
        messages = self._prepare_messages_text(prompt, text)
        response = self._generate(messages)
        elapsed = time.time() - start_time
        logger.info(f"Text analysis completed in {elapsed:.2f}s")
        return self._parse_response(response)

    def analyze_image(self, image_path: Union[str, Path], prompt: str) -> DisasterAnalysis:
        start_time = time.time()
        messages = self._prepare_messages_image(prompt, image_path)
        response = self._generate(messages)
        elapsed = time.time() - start_time
        logger.info(f"Image analysis completed in {elapsed:.2f}s")
        return self._parse_response(response)

    def analyze_frames(self, frame_paths: List[Union[str, Path]], prompt: str) -> DisasterAnalysis:
        start_time = time.time()
        messages = self._prepare_messages_frames(prompt, frame_paths)
        response = self._generate(messages)
        elapsed = time.time() - start_time
        logger.info(f"Frame analysis ({len(frame_paths)} frames) completed in {elapsed:.2f}s")
        return self._parse_response(response)

    @contextmanager
    def session(self):
        """Context manager for model session."""
        try:
            self.load()
            yield self
        finally:
            pass