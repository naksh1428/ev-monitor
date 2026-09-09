from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, CHAR, Date, DateTime, Double, ForeignKey,
    Index, Integer, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Operator(Base):
    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    stations: Mapped[list["Station"]] = relationship(back_populates="operator")


class StatusType(Base):
    __tablename__ = "status_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    title: Mapped[Optional[str]] = mapped_column(String(100))
    is_operational: Mapped[Optional[bool]] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Address(Base):
    __tablename__ = "addresses"
    __table_args__ = (
        Index("idx_addresses_town", "town", mysql_length=100),  # town is TEXT; MySQL requires a key length to index it
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    address_line1: Mapped[Optional[str]] = mapped_column(Text)
    address_line2: Mapped[Optional[str]] = mapped_column(Text)
    town: Mapped[Optional[str]] = mapped_column(Text)
    state_or_province: Mapped[Optional[str]] = mapped_column(Text)
    postcode: Mapped[Optional[str]] = mapped_column(Text)
    country_id: Mapped[Optional[int]] = mapped_column(Integer)
    latitude: Mapped[Optional[float]] = mapped_column(Double)
    longitude: Mapped[Optional[float]] = mapped_column(Double)
    contact_no: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    stations: Mapped[list["Station"]] = relationship(back_populates="address")


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)  # OCM ID
    uuid: Mapped[Optional[str]] = mapped_column(CHAR(36), unique=True)
    operator_id: Mapped[Optional[int]] = mapped_column(ForeignKey("operators.id"))
    usage_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    address_id: Mapped[Optional[int]] = mapped_column(ForeignKey("addresses.id"))
    number_of_points: Mapped[Optional[int]] = mapped_column(Integer)
    status_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("status_types.id"))
    date_created: Mapped[Optional[datetime]] = mapped_column(DateTime)  # OCM's own DateCreated
    date_last_status_update: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # when we first stored this row
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    operator: Mapped[Optional["Operator"]] = relationship(back_populates="stations")
    address: Mapped[Optional["Address"]] = relationship(back_populates="stations")
    status_type: Mapped[Optional["StatusType"]] = relationship()
    connections: Mapped[list["Connection"]] = relationship(back_populates="station")
    snapshots: Mapped[list["StatusSnapshot"]] = relationship(back_populates="station")


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)  # OCM connection ID
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False, index=True)
    connection_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    current_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    level_id: Mapped[Optional[int]] = mapped_column(Integer)
    power_kw: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    amps: Mapped[Optional[int]] = mapped_column(Integer)
    voltage: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    status_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("status_types.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    station: Mapped["Station"] = relationship(back_populates="connections")
    status_type: Mapped[Optional["StatusType"]] = relationship()


class StatusSnapshot(Base):
    __tablename__ = "status_snapshots"
    __table_args__ = (
        Index("idx_snapshots_station_checked", "station_id", "checked_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    status_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("status_types.id"))
    source_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)   # from DateLastStatusUpdate
    checked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # when your poller ran

    station: Mapped["Station"] = relationship(back_populates="snapshots")
    status_type: Mapped[Optional["StatusType"]] = relationship()


class ConnectionStatusDaily(Base):
    """One row per connection per day: was it working, plus denormalized fields for fast reporting."""

    __tablename__ = "connection_status_daily"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "connection_id", name="uq_connection_status_daily_date_connection"),
        Index("idx_csd_connection_date", "connection_id", "snapshot_date"),
        Index("idx_csd_date_working", "snapshot_date", "is_working"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    connection_id: Mapped[int] = mapped_column(ForeignKey("connections.id"), nullable=False)
    status_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("status_types.id"))
    is_working: Mapped[bool] = mapped_column(Boolean, nullable=False)
    town: Mapped[Optional[str]] = mapped_column(String(255))
    postcode: Mapped[Optional[str]] = mapped_column(String(16))
    operator_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())