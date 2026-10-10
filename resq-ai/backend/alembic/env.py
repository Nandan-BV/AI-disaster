import asyncio
from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.database import Base
from app.models import (
    CopilotConversation,
    CopilotMessage,
    EnvironmentalConditions,
    Event,
    EventAIAnalysis,
    Evidence,
    Incident,
    IncidentAnalysisArea,
    IncidentEvent,
    IncidentInvestigation,
    ImpactAssessment,
    Infrastructure,
    OptimizationHistory,
    OptimizationResult,
    PopulationZone,
    Resource,
    ResourceAllocation,
    ResourceDemand,
    RiskAssessment,
    RiskAssessmentHistory,
    User,
)

_MODEL_CLASSES = (
    CopilotConversation,
    CopilotMessage,
    EnvironmentalConditions,
    Event,
    EventAIAnalysis,
    Evidence,
    Incident,
    IncidentAnalysisArea,
    IncidentEvent,
    IncidentInvestigation,
    ImpactAssessment,
    Infrastructure,
    OptimizationHistory,
    OptimizationResult,
    PopulationZone,
    Resource,
    ResourceAllocation,
    ResourceDemand,
    RiskAssessment,
    RiskAssessmentHistory,
    User,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))
target_metadata = Base.metadata
if {model.__table__ for model in _MODEL_CLASSES} != set(target_metadata.tables.values()):
    raise RuntimeError("Alembic model imports do not match Base.metadata.")


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
