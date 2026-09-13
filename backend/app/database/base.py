from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

# Ensure JSONB works in SQLite for testing
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"
