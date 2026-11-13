"""
Security guardrails: untrusted-content delimiters, injection pattern detection, secret scrubbing.
"""

import html
import re
from collections.abc import Sequence
from typing import Any

from app.core.security_events import security_event

# Prompt injection signatures (case-insensitive)
INJECTION_PATTERNS = [
    re.compile(
        r"\b(ignore|disregard|forget|override)\s+(all\s+)?(previous|prior|system)\s+(instructions|prompts|rules)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(system\s+prompt|developer\s+mode|jailbreak|DAN\s+mode)\b", re.IGNORECASE),
    re.compile(
        r"\b(reveal|output|display|leak)\s+(your\s+)?(secret|token|api[_\s]key|canary|password|credentials)\b",
        re.IGNORECASE,
    ),
    re.compile(r"</?untrusted_document_context.*?>", re.IGNORECASE),
    re.compile(r"</?untrusted_tool_output.*?>", re.IGNORECASE),
]

# Sensitive Information & Secret Redaction Patterns (OWASP LLM02)
SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Private Key blocks
    (
        # The body may not contain "--", so a stray BEGIN header cannot scan to the end of the file.
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
            r"(?:[^-]|-(?!--)){0,16384}?"
            r"-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    # AWS Access Key ID
    (re.compile(r"\b(AKIA[0-9A-Z]{16})\b"), "[REDACTED_AWS_KEY]"),
    # AWS Secret Key assignments
    (
        re.compile(
            r"(?i)\b(aws_secret_access_key|secret_key|aws_secret)\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"
        ),
        r"\1=[REDACTED_AWS_SECRET]",
    ),
    # JWT tokens
    (
        # Start only at the beginning of a token and bound each segment so matching stays linear.
        re.compile(
            r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,8192}"
            r"\.[A-Za-z0-9_-]{10,8192}\.[A-Za-z0-9_-]{10,8192}(?![A-Za-z0-9_-])"
        ),
        "[REDACTED_JWT_TOKEN]",
    ),
    # OpenAI, Anthropic, or GitHub tokens
    (
        re.compile(r"\b(sk-[a-zA-Z0-9_-]{20,}|ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{22,})\b"),
        "[REDACTED_API_KEY]",
    ),
    # Google API keys (Gemini and other Google APIs). The body is exactly 35 characters.
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"), "[REDACTED_GOOGLE_API_KEY]"),
    # Database URIs with credentials
    (
        re.compile(
            r"(?<![A-Za-z0-9])(postgresql|postgres|mysql|mongodb|redis)://"
            r"([^:\s@/]{1,128}):([^@\s]{1,256})@"
        ),
        r"\1://\2:[REDACTED_PASSWORD]@",
    ),
]


def scrub_sensitive_information(text: str, preserve_lines: bool = False) -> str:
    """
    Scrub credentials, API keys, JWTs, and private keys from untrusted document text.
    Mitigates OWASP LLM02 (Sensitive Information Disclosure).

    With ``preserve_lines`` a multi-line redaction keeps its newline count, so line
    numbers computed on the scrubbed text still match the original document.
    """
    if not text:
        return ""
    scrubbed = text
    for pattern, replacement in SECRET_PATTERNS:
        if preserve_lines:
            scrubbed = pattern.sub(
                lambda m, r=replacement: m.expand(r) + "\n" * m.group(0).count("\n"),
                scrubbed,
            )
        else:
            scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


def sanitize_untrusted_text(text: str) -> str:
    """
    Sanitize text retrieved from external or user-uploaded documents to prevent delimiter breakout attacks.
    Escapes any closing or opening XML-style tags that mimic untrusted_document_context or untrusted_tool_output.
    """
    if not text:
        return ""
    # Neutralize any attempts to prematurely close or spoof document delimiters
    sanitized = re.sub(
        r"</?untrusted_(?:document_context|tool_output)[^>]*>",
        lambda m: html.escape(m.group(0)),
        text,
        flags=re.IGNORECASE,
    )
    return sanitized


# Stored and shown in place of a passage that matches the injection patterns.
WITHHELD_PASSAGE = "[withheld: this passage matched a prompt-injection pattern and was not indexed]"
_SECRET_HOLD = 256


def screen_passage(text: str) -> tuple[str | None, str | None]:
    """Return scrubbed passage text, or ``(None, reason)`` when it matches an injection pattern.

    The pattern list is a warning signal. A match is withheld from the model and from clients.
    Text that does not match is still only ever shown inside untrusted delimiters.
    """
    safe = scrub_sensitive_information(sanitize_untrusted_text(text))
    injected, reason = detect_prompt_injection(safe)
    if injected:
        return None, reason or "injection pattern"
    return safe, None


def wrap_untrusted_tool_output(content: str, tool: str) -> str:
    """Wrap text that came from a tool (for example web search) so the model treats it as data."""
    safe, reason = screen_passage(content)
    if safe is None:
        safe = "This tool result was withheld because it matched a prompt-injection pattern."
        security_event("injection.flagged", filename=tool, reason=reason or "injection pattern")
    return (
        f'<untrusted_tool_output tool="{html.escape(tool)}">\n'
        f"{safe.strip()}\n"
        "</untrusted_tool_output>"
    )


def wrap_untrusted_context(
    content: str,
    filename: str = "document.md",
    page: int | None = None,
    doc_id: str | None = None,
    label: str | None = None,
) -> str:
    """
    Wrap untrusted retrieved document content with strict XML-style security boundaries.
    Instructs models to treat content within boundaries strictly as passive data, never instructions.
    """
    safe_content = sanitize_untrusted_text(content)
    page_attr = f' page="{page}"' if page else ""
    doc_attr = f' id="{doc_id}"' if doc_id else ""
    label_attr = f' label="{html.escape(label)}"' if label else ""

    return (
        f'<untrusted_document_context{label_attr} filename="{html.escape(filename)}"{doc_attr}{page_attr}>\n'
        f"{safe_content.strip()}\n"
        f"</untrusted_document_context>"
    )


def detect_prompt_injection(text: str) -> tuple[bool, str | None]:
    """Flag known injection phrasing. Returns ``(is_injected, matched_reason)``.

    This is not a complete filter: a rephrased attack does not match. Callers withhold a match
    from the model and from clients, and keep every other passage inside untrusted delimiters.
    """
    if not text:
        return False, None

    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, f"Suspicious prompt pattern detected: '{match.group(0)}'"

    return False, None


def sanitize_retrieved_chunks(
    chunks: Sequence[Any],
) -> tuple[list[Any], list[dict[str, str]]]:
    """
    Defense-in-depth for indirect prompt injection arriving inside retrieved documents.

    Each kept chunk has delimiter-breakout attempts escaped and credentials scrubbed. A chunk
    that matches the injection patterns is omitted and reported, so it is not given to the model.

    Returns ``(kept_chunks, flagged)`` where ``flagged`` entries carry the filename and the reason.
    """
    flagged: list[dict[str, str]] = []
    kept: list[Any] = []
    for chunk in chunks:
        safe, reason = screen_passage(chunk.content)
        if safe is None:
            flagged.append({"filename": chunk.filename, "reason": reason or "injection pattern"})
            security_event(
                "injection.flagged", filename=chunk.filename, reason=reason or "injection pattern"
            )
            continue
        chunk.content = safe
        kept.append(chunk)
    return kept, flagged


class StreamingScrubber:
    """Scrub secrets out of a token stream before a client sees them.

    The last 256 characters stay buffered so a key that arrives split across tokens is complete
    before it is emitted. ``flush`` sends the remainder.
    """

    def __init__(self, hold: int = _SECRET_HOLD):
        self.hold = hold
        self._buf = ""

    def push(self, text: str) -> str:
        self._buf += text
        if len(self._buf) <= self.hold:
            return ""
        head, tail = self._buf[: -self.hold], self._buf[-self.hold :]
        combined = scrub_sensitive_information(head + tail)
        scrubbed_tail = scrub_sensitive_information(tail)
        if scrubbed_tail and combined.endswith(scrubbed_tail):
            ready = combined[: -len(scrubbed_tail)]
            self._buf = tail
        else:
            # A secret crossed the cut. The combined scrub already removed it, so send that.
            ready = combined
            self._buf = ""
        return ready

    def flush(self) -> str:
        ready = scrub_sensitive_information(self._buf)
        self._buf = ""
        return ready
