"""Additive registry upgrade; existing point plots and all historical IDs remain intact."""

from sqlalchemy import text

from src.db.models import farm_registry


def upgrade(connection):
    tables = [
        farm_registry.Territory,
        farm_registry.TerritoryAssignment,
        farm_registry.Farmer,
        farm_registry.RegisteredPlot,
        farm_registry.FarmerPlot,
        farm_registry.CropSeason,
        farm_registry.FarmObservation,
        farm_registry.PlotRun,
    ]
    if connection.dialect.name == "postgresql":
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public"))
        connection.execute(text("SELECT set_config('search_path', current_setting('search_path') || ', public', true)"))
    for model in tables:
        model.__table__.create(connection, checkfirst=True)
    if connection.dialect.name == "postgresql":
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_connector_jobs_plot_ids ON connector_jobs USING gin ((request::jsonb -> 'plot_ids'))"
            )
        )
        for table in ("registry_territories", "registry_plots"):
            connection.execute(
                text(f"""ALTER TABLE {table} ADD COLUMN IF NOT EXISTS geom
                geometry(Geometry,4326) GENERATED ALWAYS AS
                (ST_SetSRID(ST_GeomFromGeoJSON(boundary::text),4326)) STORED""")
            )
            connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_geom ON {table} USING gist(geom)"))
            connection.execute(
                text(f"""DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{table}_valid' AND conrelid = '{table}'::regclass) THEN
                  ALTER TABLE {table} ADD CONSTRAINT {table}_valid CHECK
                  (ST_IsValid(geom) AND NOT ST_IsEmpty(geom) AND ST_GeometryType(geom) IN ('ST_Polygon','ST_MultiPolygon'));
                END IF; END $$""")
            )
