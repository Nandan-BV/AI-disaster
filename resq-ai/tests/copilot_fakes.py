"""
Test doubles for copilot tool tests.

The copilot tools run against PostGIS and Postgres, which are not available in
the unit-test environment. These fakes let the tool *logic* be tested -
result shaping, availability reporting, validation, and the refusal paths -
without pretending to test the database itself. The SQL itself is fixed text
executed by the real engine at runtime.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.sql.elements import TextClause


class _Scalars:
    def __init__(self, rows: List[Any]) -> None:
        self._rows = rows

    def all(self) -> List[Any]:
        out = []
        for row in self._rows:
            # Unwrap single-entity rows so callers get model instances.
            if isinstance(row, tuple) and len(row) == 1:
                out.append(row[0])
            else:
                out.append(row)
        return out

    def first(self) -> Optional[Any]:
        rows = self.all()
        return rows[0] if rows else None


class _Mappings:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    def all(self) -> List[Dict[str, Any]]:
        return list(self._rows)

    def first(self) -> Optional[Dict[str, Any]]:
        return self._rows[0] if self._rows else None


class FakeResult:
    """Mimics the SQLAlchemy result object the tools consume."""

    def __init__(self, rows: Optional[List[Any]] = None) -> None:
        self._rows = rows or []

    def scalar_one_or_none(self) -> Optional[Any]:
        return self._rows[0] if self._rows else None

    def scalar_one(self) -> Any:
        return self._rows[0] if self._rows else None

    def scalar(self) -> Any:
        return self._rows[0] if self._rows else None

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)

    def mappings(self) -> _Mappings:
        return _Mappings(self._rows)

    def all(self) -> List[Any]:
        return list(self._rows)

    def first(self) -> Optional[Any]:
        return self._rows[0] if self._rows else None


class FakeSession:
    """Minimal AsyncSession stand-in driven by preconfigured rows.

    Args:
        objects: model class -> list of instances returned for selects/gets.
        text_results: substring of the SQL -> list of row dicts, for raw queries.
        scalar: value returned for aggregate selects such as ``max(sequence)``.
    """

    def __init__(
        self,
        objects: Optional[Dict[type, List[Any]]] = None,
        text_results: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        scalar: Any = 0,
    ) -> None:
        self.objects = objects or {}
        self.text_results = text_results or {}
        self.scalar = scalar
        self.committed = 0
        self.added: List[Any] = []
        self.executed_sql: List[str] = []

    async def get(self, model: type, pk: Any) -> Optional[Any]:
        for instance in self.objects.get(model, []):
            if getattr(instance, "id", None) == pk:
                return instance
        return None

    async def execute(self, statement: Any, params: Any = None) -> FakeResult:
        if isinstance(statement, TextClause):
            sql = str(statement)
            self.executed_sql.append(sql)
            for needle, rows in self.text_results.items():
                if needle in sql:
                    return FakeResult(rows)
            return FakeResult([])

        # Aggregate select (e.g. coalesce(max(sequence), 0)) has no entity.
        entity = self._first_entity(statement)
        if entity is None:
            return FakeResult([self.scalar])

        rows = list(self.objects.get(entity, []))

        # Emulate the equality filters the ORM puts in WHERE, so tools that
        # query a child table by parent id see only that parent's rows.
        rows = self._apply_bind_filters(rows, self._bind_values(statement))

        limit = self._limit(statement)
        if limit is not None:
            rows = rows[:limit]
        return FakeResult(rows)

    @staticmethod
    def _bind_values(statement: Any) -> List[Any]:
        """Collect literal values from the statement's WHERE clause."""
        try:
            clause = statement.whereclause
            if clause is None:
                return []
            values = []
            for value in clause.compile().params.values():
                if value is None or isinstance(value, (dict, list)):
                    continue
                values.append(value)
            return values
        except Exception:  # pragma: no cover - unparseable clause
            return []

    @staticmethod
    def _apply_bind_filters(rows: List[Any], bind_values: List[Any]) -> List[Any]:
        if not bind_values or not rows:
            return rows

        def attributes_of(row: Any) -> Dict[str, Any]:
            # Rows may be model instances or tuples of instances (multi-entity
            # selects); flatten both into one comparable mapping.
            items = row if isinstance(row, tuple) else (row,)
            attributes: Dict[str, Any] = {}
            for item in items:
                if hasattr(item, "__dict__"):
                    attributes.update(
                        {
                            name: value
                            for name, value in vars(item).items()
                            if not name.startswith("_")
                        }
                    )
            return attributes

        def matches(row: Any) -> bool:
            attributes = attributes_of(row)
            return all(
                any(attribute == value for attribute in attributes.values())
                for value in bind_values
            )

        return [row for row in rows if matches(row)]

    @staticmethod
    def _first_entity(statement: Any) -> Optional[type]:
        try:
            descriptions = statement.column_descriptions
        except Exception:  # pragma: no cover - non-select statement
            return None
        for description in descriptions:
            if description.get("entity") is not None:
                return description["entity"]
        return None

    @staticmethod
    def _limit(statement: Any) -> Optional[int]:
        clause = getattr(statement, "_limit_clause", None)
        if clause is None:
            return None
        try:
            value = clause.value
        except Exception:  # pragma: no cover
            return None
        return int(value) if isinstance(value, (int, float)) else None

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed += 1

    async def delete(self, instance: Any) -> None:
        return None


class ScriptedLLMClient:
    """An LLM client that replays a fixed script of responses.

    Lets the copilot's tool loop, prompt assembly, and refusal behaviour be
    tested without a model server. Every call is recorded so tests can assert
    on exactly what would have been sent to the model.
    """

    def __init__(self, script: List[Any], model_name: str = "scripted-copilot") -> None:
        self._script = list(script)
        self._model_name = model_name
        self.calls: List[Dict[str, Any]] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        return True

    async def chat_completion(self, messages: Any, tools: Any = None, **kwargs: Any):
        from app.ai.llm.base import ChatCompletionResponse

        self.calls.append({"messages": list(messages), "tools": tools})
        if not self._script:
            raise AssertionError(
                f"ScriptedLLMClient ran out of responses after {len(self.calls)} call(s)."
            )
        item = self._script.pop(0)
        if callable(item):
            item = item(messages)
        return item

    async def chat_completion_stream(self, messages: Any, tools: Any = None, **kwargs: Any):
        response = await self.chat_completion(messages, tools, **kwargs)
        yield response.content
