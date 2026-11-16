"""Rewrite FastAPI ``name: T = Depends(x)`` parameters to ``name: Annotated[T, Depends(x)]``."""

import ast
import re
import sys

MARKERS = "Depends|Security|File|Form|Header|Cookie|Body|Path"
pat_simple = re.compile(rf"(?P<name>\w+): (?P<type>[^=:,\n]+?) = (?P<call>(?:{MARKERS})\((?P<args>[^()]*(?:\([^()]*\)[^()]*)*)\))")
pat_query = re.compile(r"(?P<name>\w+): (?P<type>[^=:,\n]+?) = Query\((?P<default>[^,()]+)(?:, (?P<rest>[^()]*))?\)")

for path in sys.argv[1:]:
    raw = open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    src = raw.replace("\r\n", "\n")

    def simple(m: re.Match[str]) -> str:
        call = m["call"]
        if call == "File(...)":
            call = "File()"
        return f"{m['name']}: Annotated[{m['type'].strip()}, {call}]"

    def query(m: re.Match[str]) -> str:
        rest = m["rest"]
        q = f"Query({rest})" if rest else "Query()"
        return f"{m['name']}: Annotated[{m['type'].strip()}, {q}] = {m['default'].strip()}"

    out = pat_query.sub(query, src)
    out = pat_simple.sub(simple, out)
    if out == src:
        continue
    if not re.search(r"^from typing import .*\bAnnotated\b", out, re.M):
        if re.search(r"^from typing import ", out, re.M):
            out = re.sub(r"^from typing import (.*)$", r"from typing import Annotated, \1", out, count=1, flags=re.M)
        else:
            first = re.search(r"^(import|from) ", out, re.M)
            assert first
            out = out[: first.start()] + "from typing import Annotated\n" + out[first.start():]
    try:
        ast.parse(out)
    except SyntaxError as e:
        print("SKIP (param order)", path, e.lineno)
        continue
    open(path, "w", encoding="utf-8", newline="").write(out.replace("\n", "\r\n") if crlf else out)
    print("rewrote", path)
