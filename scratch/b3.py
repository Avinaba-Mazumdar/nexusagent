from ed import rep

rep("app/rag/ingest.py", "    docs = []\n", "    docs: list[LIDocument] = []\n")
rep("app/rag/ingest.py", "    chunks = []\n", "    chunks: list[DocumentChunk] = []\n")
rep(
    "app/rag/ingest.py",
    """        header = node.metadata.get("header_path", "")
        meta = {
            "filename": filename,
            "headerPath": [h for h in str(header).split("/") if h],
            "page": node.metadata.get("page"),
        }""",
    """        header = cast(object, node.metadata.get("header_path", ""))
        meta: dict[str, object] = {
            "filename": filename,
            "headerPath": [h for h in str(header).split("/") if h],
            "page": cast(object, node.metadata.get("page")),
        }""",
)
rep("app/rag/ingest.py", "import io\n", "import io\nfrom typing import cast\n")

rep("app/agent/model_health.py", "_pending_writes: set[asyncio.Task] = set()", "_pending_writes: set[asyncio.Task[None]] = set()")
rep(
    "app/agent/model_health.py",
    """        by_scope.setdefault(row["scope"], {})[row["model"]] = row["retry_after"].timestamp()""",
    """        retry_after = col_datetime(row, "retry_after").timestamp()
        by_scope.setdefault(col_str(row, "scope"), {})[col_str(row, "model")] = retry_after""",
)
rep("app/agent/model_health.py", "from app.db.neon import DatabaseUnavailable, neon_db\n", "from app.db.neon import DatabaseUnavailable, neon_db\nfrom app.db.records import col_datetime, col_str\n")

rep(
    "app/db/records.py",
    "def col_opt_datetime(row: Record, key: str) -> datetime | None:",
    '''def col_datetime(row: Record, key: str) -> datetime:
    value = col_opt_datetime(row, key)
    if value is None:
        raise TypeError(f"column {key!r} is NULL")
    return value


def col_opt_datetime(row: Record, key: str) -> datetime | None:''',
)
print("ok")
