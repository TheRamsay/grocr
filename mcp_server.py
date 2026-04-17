import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
from sqlalchemy import text
from db.models import init_db, get_session

mcp = FastMCP("grocr")
engine = init_db()

SCHEMA = """
Tables:
- receipts(id, store, receipt_id, date, total_czk, raw_json)
- receipt_items(id, receipt_pk, name, quantity, unit_price_czk, total_price_czk)
- store_tokens(store, access_token, refresh_token)
- sync_log(id, store, started_at, finished_at, new_receipts, status, error)

receipts.id = '<store>:<receipt_id>'
receipt_items.receipt_pk references receipts.id
date is stored as timestamptz string, cast with ::timestamptz
Stores: albert (more coming)
Currency: CZK
"""


@mcp.tool()
def get_schema() -> str:
    """Returns the grocr database schema."""
    return SCHEMA


@mcp.tool()
def query_db(sql: str) -> str:
    """
    Run a read-only SQL query against the grocr PostgreSQL database.
    Only SELECT statements are allowed.
    """
    sql = sql.strip()
    if not sql.upper().startswith("SELECT"):
        return "Error: only SELECT queries are allowed."
    try:
        with get_session(engine) as session:
            result = session.execute(text(sql))
            rows = result.fetchall()
            cols = list(result.keys())
            if not rows:
                return "No results."
            lines = ["\t".join(cols)]
            lines += ["\t".join(str(v) for v in row) for row in rows]
            return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
