"""Mechanical fixes driven by basedpyright's JSON output.

- reportUnusedCallResult: prefix the expression statement with ``_ = ``.
- reportUnannotatedClassAttribute for ``model_config = ConfigDict(``: annotate as ClassVar[ConfigDict].
- reportUnannotatedClassAttribute for ``self.x = x`` where ``x`` is an annotated parameter of the
  enclosing function: copy the parameter's annotation onto the attribute.
Line endings are preserved. Usage: python codemod.py bp.json [path-filter]
"""

import ast
import json
import os
import re
import sys
from collections import defaultdict

data = json.load(open(sys.argv[1], encoding="utf-8"))
flt = os.path.normpath(sys.argv[2]) if len(sys.argv) > 2 else ""

by_file: dict[str, list[dict]] = defaultdict(list)
for d in data["generalDiagnostics"]:
    if flt and flt not in os.path.normpath(d["file"]):
        continue
    by_file[d["file"]].append(d)


def param_annotations(tree: ast.Module, src: str) -> dict[int, dict[str, str]]:
    """line number (0-based) -> {param name: annotation source} of the enclosing function."""
    out: dict[int, dict[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            anns = {}
            a = node.args
            for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs]:
                if arg.annotation is not None:
                    anns[arg.arg] = ast.get_source_segment(src, arg.annotation)
            end = node.end_lineno or node.lineno
            for ln in range(node.lineno - 1, end):
                out[ln] = anns
    return out


changed = 0
for path, diags in by_file.items():
    raw = open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    src = raw.replace("\r\n", "\n")
    lines = src.split("\n")
    tree = ast.parse(src)
    params = param_annotations(tree, src)
    edits: dict[int, str] = {}
    for d in diags:
        rule = d.get("rule")
        ln = d["range"]["start"]["line"]
        col = d["range"]["start"]["character"]
        line = edits.get(ln, lines[ln])
        if rule == "reportUnusedCallResult":
            if line[:col].strip() == "" and not line[col:].startswith("_ ="):
                edits[ln] = line[:col] + "_ = " + line[col:]
        elif rule == "reportUnannotatedClassAttribute":
            m = re.match(r"^(\s*)model_config = ConfigDict\(", line)
            if m:
                edits[ln] = line.replace("model_config = ", "model_config: ClassVar[ConfigDict] = ", 1)
                continue
            m = re.match(r"^(\s*)self\.(\w+) = (.+)$", line)
            if m:
                indent, attr, rhs = m.groups()
                name = rhs.strip()
                ann = params.get(ln, {}).get(name)
                if ann is None:
                    # `x or default` / `list(x)` style: fall back to the param named like the attr.
                    base = params.get(ln, {}).get(attr.lstrip("_"))
                    if base is not None and re.fullmatch(rf"(list|tuple|set|dict)\({attr.lstrip('_')}\)", name):
                        ann = base.replace("Sequence", "list").replace("Iterable", "list")
                if ann is not None:
                    edits[ln] = f"{indent}self.{attr}: {ann} = {rhs}"
    if not edits:
        continue
    for ln, text in edits.items():
        lines[ln] = text
    out = "\n".join(lines)
    if "ClassVar[ConfigDict]" in out and not re.search(r"^from typing import .*\bClassVar\b", out, re.M):
        if re.search(r"^from typing import ", out, re.M):
            out = re.sub(r"^from typing import (.*)$", r"from typing import ClassVar, \1", out, count=1, flags=re.M)
        else:
            out = "from typing import ClassVar\n" + out
    open(path, "w", encoding="utf-8", newline="").write(out.replace("\n", "\r\n") if crlf else out)
    changed += 1
    print(f"{len(edits):4d} edits  {os.path.relpath(path)}")
print("files changed:", changed)
