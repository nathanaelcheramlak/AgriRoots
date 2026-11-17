"""Revision 5: additive private image metadata and duplicate-spend prevention."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, String, Table, UniqueConstraint

metadata = MetaData()
Table("users", metadata, Column("user_id", String(36), primary_key=True))
Table("offices", metadata, Column("id", String(36), primary_key=True))
assets = Table(
    "connector_image_assets",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("office_id", String(36), ForeignKey("offices.id"), nullable=False, index=True),
    Column("created_by", String(36), ForeignKey("users.user_id"), nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("media_type", String(32), nullable=False),
    Column("byte_size", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
receipts = Table(
    "connector_diagnosis_receipts",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("office_id", String(36), ForeignKey("offices.id"), nullable=False),
    Column("image_sha256", String(64), nullable=False),
    Column("provider", String(40), nullable=False),
    Column("invocation_id", String(36), nullable=False),
    Column("state", String(30), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("office_id", "image_sha256", "provider"),
)


def upgrade(connection):
    metadata.create_all(connection, tables=[assets, receipts])
