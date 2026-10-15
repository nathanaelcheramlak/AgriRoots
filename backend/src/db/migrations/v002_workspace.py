"""Frozen schema for v002_workspace. Do not change applied revisions."""
from sqlalchemy import (MetaData, Table, Column, ForeignKey, UniqueConstraint,
                        String, Integer, DateTime, JSON)

metadata = MetaData()
Table("users", metadata, Column("user_id", String(36), primary_key=True))

Table('workspace_administrators', metadata,
    Column('user_id', String(length=36), ForeignKey('users.user_id'), primary_key=True, nullable=False),
)

Table('offices', metadata,
    Column('id', String(length=36), primary_key=True, nullable=False),
    Column('name', String(length=200), nullable=False),
)

Table('office_memberships', metadata,
    Column('office_id', String(length=36), ForeignKey('offices.id'), primary_key=True, nullable=False),
    Column('user_id', String(length=36), ForeignKey('users.user_id'), primary_key=True, nullable=False),
    Column('role', String(length=20), nullable=False),
    UniqueConstraint('user_id'),
)

Table('workspace_records', metadata,
    Column('id', String(length=36), primary_key=True, nullable=False),
    Column('office_id', String(length=36), ForeignKey('offices.id'), nullable=False, index=True),
    Column('farmer_user_id', String(length=36), ForeignKey('users.user_id'), nullable=True, unique=True),
    Column('kind', String(length=20), nullable=False, index=True),
    Column('data', JSON(), nullable=False),
    Column('revision', Integer(), nullable=False),
    Column('created_by', String(length=36), ForeignKey('users.user_id'), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
)

Table('advisories', metadata,
    Column('id', String(length=36), primary_key=True, nullable=False),
    Column('office_id', String(length=36), ForeignKey('offices.id'), nullable=False, index=True),
    Column('current_version', Integer(), nullable=False),
    Column('revision', Integer(), nullable=False),
)

Table('advisory_versions', metadata,
    Column('id', String(length=36), primary_key=True, nullable=False),
    Column('advisory_id', String(length=36), ForeignKey('advisories.id'), nullable=False, index=True),
    Column('version', Integer(), nullable=False),
    Column('status', String(length=20), nullable=False),
    Column('content', JSON(), nullable=False),
    Column('recipient_user_ids', JSON(), nullable=False),
    Column('evidence_snapshots', JSON(), nullable=False),
    Column('created_by', String(length=36), ForeignKey('users.user_id'), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    UniqueConstraint('advisory_id', 'version'),
)

Table('workspace_events', metadata,
    Column('id', String(length=36), primary_key=True, nullable=False),
    Column('office_id', String(length=36), ForeignKey('offices.id'), nullable=True, index=True),
    Column('actor_id', String(length=36), ForeignKey('users.user_id'), nullable=False),
    Column('entity_id', String(length=36), nullable=False, index=True),
    Column('action', String(length=40), nullable=False),
    Column('details', JSON(), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
)

TABLES = ('workspace_administrators', 'offices', 'office_memberships', 'workspace_records', 'advisories', 'advisory_versions', 'workspace_events')


def upgrade(connection):
    metadata.create_all(connection, tables=[metadata.tables[name] for name in TABLES])
