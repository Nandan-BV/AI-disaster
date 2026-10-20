from pydantic_settings import BaseSettings
from pydantic import AliasChoices, Field, field_validator, model_validator
from typing import Optional


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "RESQ-AI"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", alias="ENVIRONMENT")
    JWT_SECRET_KEY: str = Field(
        default="development-only-change-this-jwt-secret",
        alias="JWT_SECRET_KEY",
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    EXTERNAL_INGESTION_ENABLED: bool = Field(
        default=True,
        alias="EXTERNAL_INGESTION_ENABLED",
    )
    EXTERNAL_INGESTION_INTERVAL_MINUTES: int = Field(
        default=15,
        ge=10,
        le=15,
        alias="EXTERNAL_INGESTION_INTERVAL_MINUTES",
    )
    USGS_SIGNIFICANT_FEED_URL: str = Field(
        default="https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_day.geojson",
        alias="USGS_SIGNIFICANT_FEED_URL",
    )
    GDACS_FEED_URL: str = Field(
        default="https://www.gdacs.org/xml/rss.xml",
        alias="GDACS_FEED_URL",
    )
    OPENWEATHERMAP_API_KEY: Optional[str] = Field(
        default=None,
        alias="OPENWEATHERMAP_API_KEY",
    )
    OPENWEATHERMAP_API_URL: str = Field(
        default="https://api.openweathermap.org/data/3.0/onecall",
        alias="OPENWEATHERMAP_API_URL",
    )

    @model_validator(mode="after")
    def validate_jwt_secret(self):
        if self.ENVIRONMENT.lower() not in {"development", "dev", "test"} and (
            self.JWT_SECRET_KEY == "development-only-change-this-jwt-secret"
            or len(self.JWT_SECRET_KEY) < 32
        ):
            raise ValueError(
                "Set JWT_SECRET_KEY to a unique secret of at least 32 characters "
                "outside development."
            )
        return self
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_HOST: str = Field(default="localhost", alias="DATABASE_HOST")
    DATABASE_PORT: int = Field(default=5432, alias="DATABASE_PORT")
    DATABASE_USER: str = Field(default="postgres", alias="DATABASE_USER")
    DATABASE_PASSWORD: str = Field(default="", alias="DATABASE_PASSWORD")
    DATABASE_NAME: str = Field(default="resq_ai", alias="DATABASE_NAME")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
    
    @property
    def DATABASE_URL_SYNC(self) -> str:
        return f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
    
    # CORS
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000"], alias="CORS_ORIGINS")
    
    # Geospatial Configuration (Phase 5)
    DEFAULT_INCIDENT_RADIUS_METERS: float = Field(default=1000.0, alias="DEFAULT_INCIDENT_RADIUS_METERS")
    MAX_INFRASTRUCTURE_RADIUS_METERS: float = Field(default=5000.0, alias="MAX_INFRASTRUCTURE_RADIUS_METERS")
    
    # Resource Configuration (Phase 7)
    DEFAULT_RESOURCE_SEARCH_RADIUS_METERS: float = Field(default=2000.0, alias="DEFAULT_RESOURCE_SEARCH_RADIUS_METERS")
    MAX_RESOURCE_SEARCH_RADIUS_METERS: float = Field(default=10000.0, alias="MAX_RESOURCE_SEARCH_RADIUS_METERS")
    
    # Command Center Dashboard Configuration (Phase 10)
    # Polling only — the backend has no push/live feed. This is a period, not
    # a real-time guarantee.
    DASHBOARD_REFRESH_INTERVAL_SECONDS: int = Field(default=30, alias="DASHBOARD_REFRESH_INTERVAL_SECONDS")
    DASHBOARD_DEFAULT_PAGE_SIZE: int = Field(default=20, alias="DASHBOARD_DEFAULT_PAGE_SIZE")
    DASHBOARD_MAX_PAGE_SIZE: int = Field(default=100, alias="DASHBOARD_MAX_PAGE_SIZE")

    # Optimization Configuration (Phase 8)
    MAX_RESOURCE_ALLOCATION_DISTANCE_METERS: float = Field(default=50000.0, alias="MAX_RESOURCE_ALLOCATION_DISTANCE_METERS")
    
    # Optimization Weights
    OPT_WEIGHT_DISTANCE: float = Field(default=0.3, alias="OPT_WEIGHT_DISTANCE")
    OPT_WEIGHT_SUITABILITY: float = Field(default=0.4, alias="OPT_WEIGHT_SUITABILITY")
    OPT_WEIGHT_UNMET_DEMAND: float = Field(default=0.2, alias="OPT_WEIGHT_UNMET_DEMAND")
    OPT_WEIGHT_PRIORITY: float = Field(default=0.1, alias="OPT_WEIGHT_PRIORITY")
    
    # Solver Configuration
    OPT_SOLVER_TIME_LIMIT_SECONDS: int = Field(default=30, alias="OPT_SOLVER_TIME_LIMIT_SECONDS")
    
    # LLM Configuration (Phase 9)
    # The compatible client talks to the local Ollama OpenAI-compatible API by
    # default; no OpenAI SDK or API key is required.
    #   "transformers"     -> in-process transformers loading (development only).
    #   "mock"             -> deterministic offline stub used by the test suite.
    COPILOT_PROVIDER: str = Field(default="openai_compatible", alias="COPILOT_PROVIDER")
    COPILOT_MODEL_NAME: str = Field(default="qwen2.5-coder:7b", alias="COPILOT_MODEL_NAME")
    COPILOT_MODEL_REVISION: str = Field(default="main", alias="COPILOT_MODEL_REVISION")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    COPILOT_API_BASE_URL: Optional[str] = Field(default=None, alias="COPILOT_API_BASE_URL")
    # Optional. Empty by default so no external credential is required. If a local
    # server enforces a placeholder key, set it here or in the environment.
    COPILOT_API_KEY: Optional[str] = Field(default=None, alias="COPILOT_API_KEY")
    COPILOT_DEVICE: str = Field(default="auto", alias="COPILOT_DEVICE")
    COPILOT_DTYPE: str = Field(default="auto", alias="COPILOT_DTYPE")
    COPILOT_MAX_MEMORY: Optional[str] = Field(default=None, alias="COPILOT_MAX_MEMORY")
    COPILOT_OFFLOAD_FOLDER: Optional[str] = Field(default=None, alias="COPILOT_OFFLOAD_FOLDER")
    COPILOT_MAX_TOKENS: int = Field(
        default=2048,
        validation_alias=AliasChoices("COPILOT_MAX_TOKENS", "COPILOT_MAX_NEW_TOKENS"),
    )
    COPILOT_TEMPERATURE: float = Field(default=0.1, alias="COPILOT_TEMPERATURE")
    COPILOT_TOP_P: float = Field(default=0.9, alias="COPILOT_TOP_P")
    COPILOT_DO_SAMPLE: bool = Field(default=False, alias="COPILOT_DO_SAMPLE")
    COPILOT_MAX_HISTORY_MESSAGES: int = Field(default=20, alias="COPILOT_MAX_HISTORY_MESSAGES")
    COPILOT_MAX_HISTORY_TOKENS: int = Field(default=8192, alias="COPILOT_MAX_HISTORY_TOKENS")
    COPILOT_TIMEOUT_SECONDS: int = Field(default=120, alias="COPILOT_TIMEOUT_SECONDS")
    # Guardrail: the copilot may run the optimizer (recommendation only) but must
    # never approve, dispatch, or mutate resource state. Keep this non-optional.
    COPILOT_ALLOW_CONTROLLED_ACTIONS: bool = Field(default=False, alias="COPILOT_ALLOW_CONTROLLED_ACTIONS")
    
    # Risk Assessment Configuration (Phase 6)
    RISK_WEIGHT_SEVERITY: float = Field(default=0.25, alias="RISK_WEIGHT_SEVERITY")
    RISK_WEIGHT_EVIDENCE: float = Field(default=0.20, alias="RISK_WEIGHT_EVIDENCE")
    RISK_WEIGHT_POPULATION: float = Field(default=0.25, alias="RISK_WEIGHT_POPULATION")
    RISK_WEIGHT_INFRASTRUCTURE: float = Field(default=0.15, alias="RISK_WEIGHT_INFRASTRUCTURE")
    RISK_WEIGHT_ENVIRONMENT: float = Field(default=0.10, alias="RISK_WEIGHT_ENVIRONMENT")
    RISK_WEIGHT_ACCESSIBILITY: float = Field(default=0.05, alias="RISK_WEIGHT_ACCESSIBILITY")
    
    # Risk Level Thresholds (0-100 scale)
    RISK_LEVEL_LOW_MAX: int = Field(default=19, alias="RISK_LEVEL_LOW_MAX")
    RISK_LEVEL_MODERATE_MAX: int = Field(default=39, alias="RISK_LEVEL_MODERATE_MAX")
    RISK_LEVEL_ELEVATED_MAX: int = Field(default=59, alias="RISK_LEVEL_ELEVATED_MAX")
    RISK_LEVEL_HIGH_MAX: int = Field(default=79, alias="RISK_LEVEL_HIGH_MAX")
    # 80-100 = critical
    
    # Infrastructure Criticality Weights
    INFRA_WEIGHT_HOSPITAL: float = Field(default=10.0, alias="INFRA_WEIGHT_HOSPITAL")
    INFRA_WEIGHT_SHELTER: float = Field(default=8.0, alias="INFRA_WEIGHT_SHELTER")
    INFRA_WEIGHT_FIRE_STATION: float = Field(default=6.0, alias="INFRA_WEIGHT_FIRE_STATION")
    INFRA_WEIGHT_POLICE_STATION: float = Field(default=5.0, alias="INFRA_WEIGHT_POLICE_STATION")
    INFRA_WEIGHT_BRIDGE: float = Field(default=7.0, alias="INFRA_WEIGHT_BRIDGE")
    INFRA_WEIGHT_ROAD: float = Field(default=3.0, alias="INFRA_WEIGHT_ROAD")
    INFRA_WEIGHT_EMERGENCY_CENTER: float = Field(default=8.0, alias="INFRA_WEIGHT_EMERGENCY_CENTER")
    INFRA_WEIGHT_POWER_STATION: float = Field(default=6.0, alias="INFRA_WEIGHT_POWER_STATION")
    INFRA_WEIGHT_WATER_FACILITY: float = Field(default=6.0, alias="INFRA_WEIGHT_WATER_FACILITY")
    INFRA_WEIGHT_SCHOOL: float = Field(default=4.0, alias="INFRA_WEIGHT_SCHOOL")
    
    @field_validator("DASHBOARD_REFRESH_INTERVAL_SECONDS")
    @classmethod
    def _validate_refresh_interval(cls, value: int) -> int:
        if value < 5:
            raise ValueError("DASHBOARD_REFRESH_INTERVAL_SECONDS must be >= 5")
        return value

    @field_validator("DASHBOARD_DEFAULT_PAGE_SIZE", "DASHBOARD_MAX_PAGE_SIZE")
    @classmethod
    def _validate_page_sizes(cls, value: int) -> int:
        if value < 1:
            raise ValueError("dashboard page sizes must be >= 1")
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()


# --- Copilot runtime helpers -------------------------------------------------
# These live here (not in the root ``ai`` package) so the backend can resolve a
# device/dtype without importing a top-level module that depends on the model
# layer. ``torch`` is imported lazily so the backend still boots on machines
# where only the HTTP-based copilot provider is used.

_TORCH_DTYPES = {
    "auto": "auto",
    "float16": "float16",
    "fp16": "float16",
    "bfloat16": "bfloat16",
    "bf16": "bfloat16",
    "float32": "float32",
    "fp32": "float32",
}


def get_device() -> str:
    """Resolve the torch device for local inference.

    Honours ``COPILOT_DEVICE``; ``auto`` picks CUDA when available.
    """
    requested = (settings.COPILOT_DEVICE or "auto").lower()
    if requested not in {"auto", "cpu", "cuda", "mps"}:
        return "cpu"

    if requested != "auto":
        return requested

    try:
        import torch
    except ImportError:
        return "cpu"

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def get_torch_dtype():
    """Resolve the torch dtype for local inference.

    Returns a ``torch.dtype``. ``auto`` maps to bfloat16 on CUDA when supported,
    otherwise float16 on CUDA and float32 on CPU.
    """
    import torch

    requested = _TORCH_DTYPES.get((settings.COPILOT_DTYPE or "auto").lower(), "auto")

    if requested != "auto":
        return getattr(torch, requested)

    if get_device() == "cuda":
        if torch.cuda.is_bf16_supported():
            return torch.bfloat16
        return torch.float16
    return torch.float32