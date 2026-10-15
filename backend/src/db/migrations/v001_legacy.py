"""Frozen schema for v001_legacy. Do not change applied revisions."""
from sqlalchemy import (MetaData, Table, Column, ForeignKey, UniqueConstraint,
                        String, Text, Integer, Boolean, DateTime, JSON, inspect, text)

metadata = MetaData()

Table('users', metadata,
    Column('user_id', String(length=36), primary_key=True, nullable=False),
    Column('phone_number', String(length=20), nullable=False, index=True, unique=True),
    Column('password_hash', String(length=255), nullable=False),
    Column('is_active', Boolean(), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False),
)

Table('user_profiles', metadata,
    Column('profile_id', String(length=36), primary_key=True, nullable=False),
    Column('user_id', String(length=36), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True, unique=True),
    Column('full_name', String(length=150), nullable=True),
    Column('phone_number', String(length=30), nullable=True),
    Column('location', String(length=255), nullable=True),
    Column('preferred_language', String(length=20), nullable=True),
    Column('user_type', String(length=50), nullable=True),
    Column('years_experience', Integer(), nullable=True),
    Column('main_goal', String(length=255), nullable=True),
    Column('crops_grown', Text(), nullable=True),
    Column('onboarding_completed', Boolean(), nullable=False),
    Column('onboarding_completed_at', DateTime(timezone=True), nullable=True),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False),
)

Table('otp_verifications', metadata,
    Column('verification_id', String(length=36), primary_key=True, nullable=False),
    Column('phone_number', String(length=20), nullable=False, index=True),
    Column('full_name', String(length=150), nullable=True),
    Column('otp_code_hash', String(length=255), nullable=False),
    Column('expires_at', DateTime(timezone=True), nullable=False),
    Column('attempts', Integer(), nullable=False),
    Column('max_attempts', Integer(), nullable=False),
    Column('verified', Boolean(), nullable=False),
    Column('verified_at', DateTime(timezone=True), nullable=True),
    Column('consumed', Boolean(), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
)

Table('phone_change_verifications', metadata,
    Column('change_id', String(length=36), primary_key=True, nullable=False),
    Column('user_id', String(length=36), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True),
    Column('new_phone_number', String(length=20), nullable=False, index=True),
    Column('otp_code_hash', String(length=255), nullable=False),
    Column('expires_at', DateTime(timezone=True), nullable=False),
    Column('attempts', Integer(), nullable=False),
    Column('max_attempts', Integer(), nullable=False),
    Column('verified', Boolean(), nullable=False),
    Column('verified_at', DateTime(timezone=True), nullable=True),
    Column('consumed', Boolean(), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
)

Table('password_reset_verifications', metadata,
    Column('reset_id', String(length=36), primary_key=True, nullable=False),
    Column('phone_number', String(length=20), nullable=False, index=True),
    Column('otp_code_hash', String(length=255), nullable=False),
    Column('expires_at', DateTime(timezone=True), nullable=False),
    Column('attempts', Integer(), nullable=False),
    Column('max_attempts', Integer(), nullable=False),
    Column('verified', Boolean(), nullable=False),
    Column('verified_at', DateTime(timezone=True), nullable=True),
    Column('consumed', Boolean(), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
)

Table('chat_sessions', metadata,
    Column('session_id', String(length=36), primary_key=True, nullable=False),
    Column('user_id', String(length=36), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True),
    Column('title', String(length=160), nullable=True),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False),
)

Table('chat_messages', metadata,
    Column('message_id', String(length=36), primary_key=True, nullable=False),
    Column('session_id', String(length=36), ForeignKey('chat_sessions.session_id', ondelete='CASCADE'), nullable=False, index=True),
    Column('sender', String(length=20), nullable=False),
    Column('content', Text(), nullable=False),
    Column('content_type', String(length=20), nullable=False),
    Column('message_content_english', Text(), nullable=True),
    Column('media_url', String(length=512), nullable=True),
    Column('language_used', String(length=100), nullable=True),
    Column('sequence_no', Integer(), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
)

Table('weather_alerts', metadata,
    Column('alert_id', String(length=36), primary_key=True, nullable=False),
    Column('user_id', String(length=36), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True),
    Column('alert_type', String(length=80), nullable=False),
    Column('severity', String(length=20), nullable=False),
    Column('title', String(length=180), nullable=False),
    Column('message', Text(), nullable=False),
    Column('action_text', Text(), nullable=True),
    Column('location_used', String(length=255), nullable=True),
    Column('raw_weather', Text(), nullable=True),
    Column('is_read', Boolean(), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
)

TABLES = ('users', 'user_profiles', 'otp_verifications', 'phone_change_verifications', 'password_reset_verifications', 'chat_sessions', 'chat_messages', 'weather_alerts')


def upgrade(connection):
    metadata.create_all(connection, tables=[metadata.tables[name] for name in TABLES])
    existing = {c["name"] for c in inspect(connection).get_columns("chat_messages")}
    chat_columns = {'content_type': 'VARCHAR(20)', 'message_content_english': 'TEXT', 'media_url': 'VARCHAR(512)', 'language_used': 'VARCHAR(100)'}
    for name, column_type in chat_columns.items():
        if name not in existing:
            connection.execute(text(f"ALTER TABLE chat_messages ADD COLUMN {name} {column_type}"))
