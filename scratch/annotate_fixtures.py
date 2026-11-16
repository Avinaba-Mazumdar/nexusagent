"""Annotate pytest fixture parameters in test functions by fixture name."""

import ast
import glob
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..", "apps", "backend")

# fixture name -> (annotation, import line needed or None)
TYPES: dict[str, tuple[str, str | None]] = {
    "monkeypatch": ("pytest.MonkeyPatch", None),
    "caplog": ("pytest.LogCaptureFixture", None),
    "fake_llm": ("FakeLLM", "from tests.conftest import FakeLLM"),
    "fake_rate_db": ("FakeUsageDb", "from tests.conftest import FakeUsageDb"),
    "web_search_on": ("None", None),
    "stream_client": ("StreamClient", None),  # alias defined in test_agent_stream.py
    "users": ("Users", None),  # alias defined in test_documents.py
    "models": ("UseModels", None),  # alias defined in test_model_router.py
    "google_signer": ("Signer", None),  # alias defined in test_auth.py
    "parse_calls": ("list[int]", None),
    "fake_db": ("_FakeCooldownDb", None),
}

for path in sorted(glob.glob(os.path.join(ROOT, "tests", "*.py"))):
    raw = open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    src = raw.replace("\r\n", "\n")
    tree = ast.parse(src)
    lines = src.split("\n")
    edits: list[tuple[int, int, str]] = []  # (line, col, text to insert)
    needed: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        is_fixture = any(
            "fixture" in ast.unparse(d) for d in node.decorator_list
        )
        if not (node.name.startswith("test_") or is_fixture):
            continue
        for arg in node.args.args:
            if arg.annotation is not None or arg.arg not in TYPES:
                continue
            ann, imp = TYPES[arg.arg]
            end_col = arg.col_offset + len(arg.arg)
            edits.append((arg.lineno - 1, end_col, f": {ann}"))
            if imp:
                needed.add(imp)
    if not edits:
        continue
    for ln, col, text in sorted(edits, reverse=True):
        lines[ln] = lines[ln][:col] + text + lines[ln][col:]
    out = "\n".join(lines)
    for imp in sorted(needed):
        mod, name = re.match(r"from (\S+) import (\S+)", imp).groups()
        if re.search(rf"^from {re.escape(mod)} import .*\b{name}\b", out, re.M):
            continue
        if os.path.basename(path) == "conftest.py":
            continue
        # after the last top-level "from app" / "import" line of the first import block
        m = list(re.finditer(r"^(from|import) [^\n]+(\n    [^\n]+)*\n(\)\n)?", out, re.M))
        anchor = m[-1].end() if m else 0
        out = out[:anchor] + imp + "\n" + out[anchor:]
    open(path, "w", encoding="utf-8", newline="").write(out.replace("\n", "\r\n") if crlf else out)
    print(f"{len(edits):3d} params  {os.path.basename(path)}")
