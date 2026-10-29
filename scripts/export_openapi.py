#!/usr/bin/env python3
"""
Write the API's OpenAPI schema to packages/contracts/openapi.json.

The schema is the single source for the TypeScript contracts: `pnpm --filter
@nexusagent/contracts generate` turns it into src/generated.ts. SSE payloads are not
route responses, so their models (SSE_WIRE_MODELS) are added to components.schemas here.

Usage:
  uv run --project apps/backend python scripts/export_openapi.py
"""

import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "apps" / "backend"))

# The schema does not depend on the environment; pin it so the output is reproducible.
os.environ.setdefault("ENVIRONMENT", "test")

from pydantic.json_schema import models_json_schema  # noqa: E402

from app.db.models import SSE_WIRE_MODELS  # noqa: E402
from app.main import app  # noqa: E402

OUTPUT = BASE_DIR / "packages" / "contracts" / "openapi.json"


def build_schema() -> dict:
    schema = app.openapi()
    _, sse_defs = models_json_schema(
        [(m, "serialization") for m in SSE_WIRE_MODELS],
        ref_template="#/components/schemas/{model}",
    )
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for name, definition in sse_defs.get("$defs", {}).items():
        components.setdefault(name, definition)
    return schema


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(build_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(BASE_DIR)}")
