"""Revision 3: durable agent runs, evidence links, call logs and public cache."""
from sqlalchemy import MetaData, Table, Column, ForeignKey, UniqueConstraint, String, Text, Integer, DateTime, JSON, Float

metadata = MetaData()
Table('users', metadata, Column('user_id', String(36), primary_key=True))
Table('offices', metadata, Column('id', String(36), primary_key=True))
Table('workspace_records', metadata, Column('id', String(36), primary_key=True))
Table('advisories', metadata, Column('id', String(36), primary_key=True))

Table('advisory_runs', metadata,
    Column('id', String(length=36), primary_key=True, nullable=False),
    Column('office_id', String(length=36), ForeignKey('offices.id'), nullable=False, index=True),
    Column('officer_id', String(length=36), ForeignKey('users.user_id'), nullable=False),
    Column('cluster_id', String(length=36), ForeignKey('workspace_records.id'), nullable=False),
    Column('request_key', String(length=64), nullable=False),
    Column('task', Text(), nullable=False),
    Column('status', String(length=30), nullable=False, index=True),
    Column('stage', String(length=40), nullable=False),
    Column('state', JSON(), nullable=False),
    Column('warnings', JSON(), nullable=False),
    Column('error', JSON(), nullable=True),
    Column('model_config', JSON(), nullable=False),
    Column('attempt', Integer(), nullable=False),
    Column('tool_calls', Integer(), nullable=False),
    Column('capability_hash', String(length=64), nullable=True),
    Column('lease_until', DateTime(timezone=True), nullable=True),
    Column('advisory_id', String(length=36), ForeignKey('advisories.id'), nullable=True, unique=True),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False),
    UniqueConstraint('office_id', 'request_key'),
)

Table('advisory_run_evidence', metadata,
    Column('run_id', String(length=36), ForeignKey('advisory_runs.id'), primary_key=True, nullable=False),
    Column('key', String(length=200), primary_key=True, nullable=False),
    Column('record_id', String(length=36), ForeignKey('workspace_records.id'), nullable=False),
)

Table('advisory_run_calls', metadata,
    Column('id', String(length=36), primary_key=True, nullable=False),
    Column('run_id', String(length=36), ForeignKey('advisory_runs.id'), nullable=False, index=True),
    Column('attempt', Integer(), nullable=False),
    Column('tool_name', String(length=80), nullable=False),
    Column('inputs', JSON(), nullable=False),
    Column('output', JSON(), nullable=True),
    Column('error', JSON(), nullable=True),
    Column('started_at', DateTime(timezone=True), nullable=False),
    Column('finished_at', DateTime(timezone=True), nullable=True),
    Column('duration_ms', Integer(), nullable=True),
    Column('usage', JSON(), nullable=False),
    Column('estimated_cost_usd', Float(), nullable=False),
)

Table('public_guidance_cache', metadata,
    Column('url', String(length=1000), primary_key=True, nullable=False),
    Column('retrieved_at', DateTime(timezone=True), nullable=False),
    Column('extract', Text(), nullable=False),
    Column('sha256', String(length=64), nullable=False),
    Column('source_license', String(length=100), nullable=False),
    Column('server_version', String(length=40), nullable=False),
)


def upgrade(connection):
    names = ('advisory_runs', 'advisory_run_evidence', 'advisory_run_calls', 'public_guidance_cache')
    metadata.create_all(connection, tables=[metadata.tables[name] for name in names])
