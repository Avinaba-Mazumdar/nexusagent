import re
import sys

p = sys.argv[1]
raw = open(p, encoding="utf-8", newline="").read()
crlf = chr(13) in raw
s = raw.replace(chr(13) + chr(10), chr(10))


def r(a, b, n=1):
    global s
    assert s.count(a) == n, (a, s.count(a))
    s = s.replace(a, b)


r("from typing import Annotated, Any, Literal\n", "from typing import Annotated, ClassVar, Literal, cast\n")
s = re.sub(r"(\n    )model_config = ConfigDict\(", r"\1model_config: ClassVar[ConfigDict] = ConfigDict(", s)
r(
    '''    def convert_vector_to_list(cls, v: Any) -> list[float] | None:
        if v is None:
            return None
        if hasattr(v, "tolist"):
            return [float(x) for x in v.tolist()]
        try:
            return [float(x) for x in v]
        except TypeError, ValueError:
            return v''',
    '''    def convert_vector_to_list(cls, v: object) -> object:
        """pgvector returns a numpy array; pydantic then validates the list as ``list[float]``."""
        tolist = cast(object, getattr(v, "tolist", None))
        return cast(object, tolist()) if callable(tolist) else v''',
)
r("def _wire_id(value: Any) -> Any:", "def _wire_id(value: object) -> object:")
r("def _wire_timestamp(value: Any) -> Any:", "def _wire_timestamp(value: object) -> object:")
r("def _wire_count(value: Any) -> Any:", "def _wire_count(value: object) -> object:")
s = s.replace("dict[str, Any]", "dict[str, object]")
s = s.replace(": Any = None", ": object = None")
assert "Any" not in re.sub(r"[A-Za-z_]Any|Any[A-Za-z_]", "", s), [l for l in s.splitlines() if "Any" in l]
open(p, "w", encoding="utf-8", newline="").write(s.replace(chr(10), chr(13) + chr(10)) if crlf else s)
print("ok")
