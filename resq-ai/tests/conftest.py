import pytest
import pytest_asyncio


pytest_plugins = ["pytest_asyncio"]


# ---------------------------------------------------------------------------
# SQLite spatial test harness
# ---------------------------------------------------------------------------
# The test suites run against in-memory SQLite because no PostgreSQL/PostGIS
# instance (or the SpatiaLite extension) is available in this environment.
# geoalchemy2 assumes SpatiaLite whenever the dialect is SQLite and emits
# ``RecoverGeometryColumn(...)`` / ``CreateSpatialIndex(...)`` during
# ``CREATE TABLE``, which fails with "no such function" on a plain SQLite
# build. The shims below let ``Base.metadata.create_all`` succeed on SQLite so
# the non-spatial integration tests can run:
#
#   1. Render ``Geometry``/``Geography`` as the plain SQLite type ``GEOMETRY``
#      (SQLite uses dynamic typing).
#   2. Neutralise geoalchemy2's SQLite DDL event handlers so it neither swaps
#      in a dummy type nor tries to recover geometry columns / build spatial
#      indexes.
#
# Spatially-dependent assertions are validated against a real PostGIS database
# (see docs/full_system_integration.md); they are expected to fail or be
# skipped on SQLite.
try:  # pragma: no cover - the packages are hard dependencies
    from sqlalchemy.ext.compiler import compiles
    from geoalchemy2.types import Geometry, Geography
    from geoalchemy2.admin import dialects

    @compiles(Geometry, "sqlite")
    def _render_geometry_as_text(type_, compiler, **kw):
        return "GEOMETRY"

    @compiles(Geography, "sqlite")
    def _render_geography_as_text(type_, compiler, **kw):
        return "GEOMETRY"

    def _noop_ddl(*args, **kwargs):
        return None

    for _handler in ("before_create", "after_create", "before_drop", "after_drop"):
        setattr(dialects.sqlite, _handler, _noop_ddl)

    # geoalchemy2 wraps geometry reads in ``ST_AsEWKB(col)`` and writes in the
    # "from text" function, both of which are SpatiaLite-only. On plain SQLite
    # we store/read geometry as WKT text instead, so those expressions become
    # identities. (Spatial operators/queries still require PostGIS.)
    def _identity_column_expression(self, col):
        return col

    def _identity_bind_expression(self, bindvalue):
        return bindvalue

    def _identity_result_processor(self, dialect, coltype):
        def _process(value):
            return value

        return _process

    for _type in (Geometry, Geography):
        _type.column_expression = _identity_column_expression
        _type.bind_expression = _identity_bind_expression
        _type.result_processor = _identity_result_processor

    # The services build geometry values with ``ST_SetSRID(ST_MakePoint(...))``.
    # Register minimal SQLite shims that emit WKT text so non-spatial inserts
    # work without SpatiaLite. Real spatial predicates (ST_Distance, ST_DWithin,
    # ...) are NOT emulated; tests that need them require PostGIS.
    from sqlalchemy import event as _sa_event
    from sqlalchemy.engine import Engine as _Engine

    def _sqlite_st_makepoint(x, y):
        return f"POINT({x} {y})"

    def _sqlite_st_setsrid(geom, srid):
        return f"SRID={int(srid)};{geom}"

    _SQLITE_SPATIAL_FUNCS = {
        "ST_MakePoint": (2, _sqlite_st_makepoint),
        "ST_SetSRID": (2, _sqlite_st_setsrid),
    }

    @_sa_event.listens_for(_Engine, "connect")
    def _register_sqlite_spatial_functions(dbapi_conn, connection_record):
        create_function = getattr(dbapi_conn, "create_function", None)
        if create_function is None:
            return
        for _name, (_nargs, _func) in _SQLITE_SPATIAL_FUNCS.items():
            create_function(_name, _nargs, _func)
except Exception:  # pragma: no cover
    pass