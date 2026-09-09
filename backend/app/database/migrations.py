from sqlalchemy import text

from app.database.connection import engine


def apply_development_migrations() -> None:
    statements = (
        "ALTER TABLE verifiable_credentials ADD COLUMN IF NOT EXISTS proof_type VARCHAR(100)",
        "ALTER TABLE verifiable_credentials ADD COLUMN IF NOT EXISTS signature TEXT",
        "ALTER TABLE verifiable_credentials ADD COLUMN IF NOT EXISTS signed_at TIMESTAMPTZ",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
