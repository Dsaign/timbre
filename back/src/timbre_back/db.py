import os

from psycopg.conninfo import make_conninfo


def conninfo(role: str) -> str:
    """Connection string for a database role; its password is <ROLE>_PASSWORD."""
    return make_conninfo(
        host=os.environ.get("DB_HOST", "db"),
        dbname="timbre",
        user=role,
        password=os.environ[f"{role.upper()}_PASSWORD"],
    )


def vector_literal(vector: list[float]) -> str:
    """pgvector's text input format, bound as a parameter and cast with ::vector."""
    return "[" + ",".join(map(str, vector)) + "]"
