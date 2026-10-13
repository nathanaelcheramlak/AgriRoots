from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


CHAT_MESSAGE_COLUMNS = {
    "content_type": "VARCHAR(20)",
    "message_content_english": "TEXT",
    "media_url": "VARCHAR(512)",
    "language_used": "VARCHAR(100)",
}


def ensure_chat_message_storage_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("chat_messages"):
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("chat_messages")
    }
    missing_columns = [
        (name, column_type)
        for name, column_type in CHAT_MESSAGE_COLUMNS.items()
        if name not in existing_columns
    ]
    if not missing_columns:
        return

    with engine.begin() as connection:
        for name, column_type in missing_columns:
            connection.execute(
                text(f"ALTER TABLE chat_messages ADD COLUMN {name} {column_type}")
            )
