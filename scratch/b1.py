from ed import rep

# conversations.py: conv["id"] is object
rep(
    "app/services/conversations.py",
    """        if not conv or "id" not in conv:
            logger.warning""",
    """        conv_id = conv.get("id")
        if not isinstance(conv_id, UUID):
            logger.warning""",
)
rep("app/services/conversations.py", "            conv[\"id\"],\n            query,", "            conv_id,\n            query,")

# rag.py metadata Any -> object
rep("app/routes/rag.py", "    metadata: dict[str, Any] = Field(default_factory=dict)", "    metadata: dict[str, object] = Field(default_factory=dict)")
rep("app/routes/rag.py", "from typing import Annotated, Any\n", "from typing import Annotated\n")

# ASGI scope values are Any
rep(
    "app/core/security_headers.py",
    '        no_store = scope["path"].startswith(AUTH_PATH_PREFIX)',
    '        no_store = cast(str, scope["path"]).startswith(AUTH_PATH_PREFIX)',
)
rep("app/core/security_headers.py", "from starlette.datastructures import MutableHeaders\n", "from typing import cast\n\nfrom starlette.datastructures import MutableHeaders\n")

rep(
    "app/core/body_limit.py",
    '        declared = dict(scope["headers"]).get(b"content-length")',
    '        headers = cast(list[tuple[bytes, bytes]], scope["headers"])\n        declared = dict(headers).get(b"content-length")',
)
rep(
    "app/core/body_limit.py",
    '                received += len(message.get("body", b""))',
    '                received += len(cast(bytes, message.get("body", b"")))',
)
rep("app/core/body_limit.py", "import json\n", "import json\nfrom typing import cast\n")

# health.py
rep(
    "app/routes/health.py",
    '                db_connected = await conn.fetchval("SELECT 1;") == 1',
    '                db_connected = cast(int | None, await conn.fetchval("SELECT 1;")) == 1',
)
rep(
    "app/routes/health.py",
    """                    engine_str = f"PostgreSQL {await conn.fetchval('SHOW server_version;')}\"""",
    """                    version = cast(str, await conn.fetchval("SHOW server_version;"))
                    engine_str = f"PostgreSQL {version}\"""",
)
rep("app/routes/health.py", '                    extensions = [r["extname"] for r in ext_rows]', '                    extensions = [col_str(r, "extname") for r in ext_rows]')
rep("app/routes/health.py", "    database = {\n", "    database: dict[str, object] = {\n")
rep("app/routes/health.py", "    payload: dict = {\n", "    payload: dict[str, object] = {\n")
rep("app/routes/health.py", "from datetime import UTC, datetime\n", "from datetime import UTC, datetime\nfrom typing import cast\n")
rep("app/routes/health.py", "from app.db.neon import neon_db\n", "from app.db.neon import neon_db\nfrom app.db.records import col_str\n")
print("ok")
