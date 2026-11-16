from ed import rep

A = "app/core/auth.py"
rep(A, "def create_access_token(data: dict, expires_delta", "def create_access_token(\n    data: Mapping[str, object], expires_delta")
rep(A, "    to_encode = data.copy()\n", "    to_encode: dict[str, object] = dict(data)\n")
rep(A, "def decode_access_token(token: str) -> dict:", "def decode_access_token(token: str) -> dict[str, object]:")
rep(A, "def session_claims(user: User, auth_time: int | None = None) -> dict:", "def session_claims(user: User, auth_time: int | None = None) -> dict[str, object]:")
rep(A, "async def resolve_session(token: str, db: NeonDatabase) -> tuple[User, dict]:", "async def resolve_session(token: str, db: NeonDatabase) -> tuple[User, dict[str, object]]:")
rep(
    A,
    """    user_id_str = payload.get("sub")
    if not user_id_str:
        raise _unauthorized("Invalid token subject")""",
    """    user_id_str = payload.get("sub")
    if not isinstance(user_id_str, str) or not user_id_str:
        raise _unauthorized("Invalid token subject")""",
)
rep(
    A,
    "async def verify_google_token(credential: str) -> dict:",
    "async def verify_google_token(credential: str) -> GoogleProfile:",
)
rep(
    A,
    """        info = jwt.decode(
            credential,
            signing_key.key,""",
    """        info = jwt.decode(
            credential,
            signing_key,""",
)
rep(
    A,
    """    email = info.get("email")
    if not email:""",
    """    email = cast(object, info.get("email"))
    if not isinstance(email, str) or not email:""",
)
rep(
    A,
    """    return {
        "email": email,
        "name": info.get("name") or email.split("@")[0],
        "picture": info.get("picture"),
        "sub": info["sub"],
    }""",
    """    name = cast(object, info.get("name"))
    picture = cast(object, info.get("picture"))
    return GoogleProfile(
        email=email,
        name=name if isinstance(name, str) and name else email.split("@")[0],
        picture=picture if isinstance(picture, str) else None,
        sub=str(cast(object, info["sub"])),
    )""",
)
rep(
    A,
    "async def verify_google_token(",
    '''class GoogleProfile(TypedDict):
    """The verified fields of a Google ID token that sign-in uses."""

    email: str
    name: str
    picture: str | None
    sub: str


async def verify_google_token(''',
)

R = "app/routes/auth.py"
rep(
    R,
    """    auth_time = int(claims.get("auth_time", claims.get("iat", 0)))""",
    """    issued = claims.get("auth_time", claims.get("iat", 0))
    auth_time = int(issued) if isinstance(issued, int | float | str) else 0""",
)

G = "app/core/security_guardrails.py"
rep(G, "SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [", "SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [")
rep(
    G,
    """            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
            r"(?:[^-]|-(?!--)){0,16384}?"
            r"-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----\"""",
    """            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
            + r"(?:[^-]|-(?!--)){0,16384}?"
            + r"-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----\"""",
)
rep(
    G,
    """            r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,8192}"
            r"\\.[A-Za-z0-9_-]{10,8192}""",
    """            r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,8192}"
            + r"\\.[A-Za-z0-9_-]{10,8192}""",
)
rep(
    G,
    """            r"(?<![A-Za-z0-9])(postgresql|postgres|mysql|mongodb|redis)://"
            r"([^:\\s@/]{1,128})""",
    """            r"(?<![A-Za-z0-9])(postgresql|postgres|mysql|mongodb|redis)://"
            + r"([^:\\s@/]{1,128})""",
)
rep(
    G,
    """            scrubbed = pattern.sub(
                lambda m, r=replacement: m.expand(r) + "\\n" * m.group(0).count("\\n"),
                scrubbed,
            )""",
    """            scrubbed = pattern.sub(_keeping_lines(replacement), scrubbed)""",
)
rep(
    G,
    "def scrub_sensitive_information(",
    '''def _keeping_lines(replacement: str) -> Callable[[re.Match[str]], str]:
    """A replacement that keeps the matched text's newline count."""

    def expand(match: re.Match[str]) -> str:
        return match.expand(replacement) + "\\n" * match.group(0).count("\\n")

    return expand


def scrub_sensitive_information(''',
)
rep(
    G,
    """def sanitize_retrieved_chunks(
    chunks: Sequence[Any],
) -> tuple[list[Any], list[dict[str, str]]]:""",
    """class Passage(Protocol):
    \"\"\"A retrieved passage: its text (rewritten in place when sanitized) and source file.\"\"\"

    content: str

    @property
    def filename(self) -> str: ...


def sanitize_retrieved_chunks[P: Passage](
    chunks: Sequence[P],
) -> tuple[list[P], list[dict[str, str]]]:""",
)
rep(G, "    kept: list[Any] = []\n", "    kept: list[P] = []\n")
rep(G, '        self._buf = ""\n', '        self._buf: str = ""\n')
print("ok")
