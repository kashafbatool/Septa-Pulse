"""Initial schema: vehicle_positions, alerts, route_stats

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "vehicle_positions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("vehicle_id", sa.String(64), nullable=False),
        sa.Column("route", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry("POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("heading", sa.Integer(), nullable=True),
        sa.Column("speed", sa.Float(), nullable=True),
        sa.Column("offset_sec", sa.Integer(), nullable=True),
        sa.Column("destination", sa.String(128), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vehicle_positions_route_fetched",
        "vehicle_positions",
        ["route", "fetched_at"],
    )
    op.create_index(
        "ix_vehicle_positions_fetched_at",
        "vehicle_positions",
        ["fetched_at"],
    )
    op.create_index(
        "ix_vehicle_positions_geom",
        "vehicle_positions",
        ["geom"],
        postgresql_using="gist",
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("route", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("advisory_message", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_alerts_route_fetched",
        "alerts",
        ["route", "fetched_at"],
    )

    op.create_table(
        "route_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("route", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("avg_delay_sec", sa.Float(), nullable=True),
        sa.Column("vehicle_count", sa.Integer(), nullable=True),
        sa.Column("on_time_pct", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_route_stats_route_snapshot",
        "route_stats",
        ["route", "snapshot_at"],
    )


def downgrade() -> None:
    op.drop_table("route_stats")
    op.drop_table("alerts")
    op.drop_table("vehicle_positions")
