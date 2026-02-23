from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class VehiclePosition(Base):
    """Real-time and historical vehicle positions from SEPTA TransitView + TrainView."""

    __tablename__ = "vehicle_positions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    vehicle_id = Column(String(64), nullable=False)
    route = Column(String(32), nullable=False)
    mode = Column(String(8), nullable=False)  # 'bus' | 'rail' | 'trolley'
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    geom = Column(Geometry("POINT", srid=4326), nullable=True)
    heading = Column(Integer, nullable=True)
    speed = Column(Float, nullable=True)
    offset_sec = Column(Integer, nullable=True)  # delay in seconds (positive = late)
    destination = Column(String(128), nullable=True)
    fetched_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_vehicle_positions_route_fetched", "route", "fetched_at"),
        Index("ix_vehicle_positions_fetched_at", "fetched_at"),
        Index("ix_vehicle_positions_geom", "geom", postgresql_using="gist"),
    )

    def __repr__(self) -> str:
        return f"<VehiclePosition route={self.route} vehicle={self.vehicle_id} at={self.fetched_at}>"


class Alert(Base):
    """SEPTA service alerts."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route = Column(String(32), nullable=False)
    message = Column(Text, nullable=True)
    advisory_message = Column(Text, nullable=True)
    fetched_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (Index("ix_alerts_route_fetched", "route", "fetched_at"),)


class RouteStats(Base):
    """Aggregated delay/efficiency statistics per route, computed every pipeline run."""

    __tablename__ = "route_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route = Column(String(32), nullable=False)
    mode = Column(String(8), nullable=False)
    snapshot_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    avg_delay_sec = Column(Float, nullable=True)
    vehicle_count = Column(Integer, nullable=True)
    on_time_pct = Column(Float, nullable=True)  # percentage 0-100

    __table_args__ = (Index("ix_route_stats_route_snapshot", "route", "snapshot_at"),)
