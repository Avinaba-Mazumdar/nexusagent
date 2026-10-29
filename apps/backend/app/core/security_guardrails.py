"""
Security Guardrails: Prompt Injection Delimiters & Canary Tokens.
Protects autonomous agent context from indirect prompt injection and data exfiltration.
"""

import hashlib
import html
import json
import re
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

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

# Sensitive Information & Secret Redaction Patterns (OWASP LLM02 / ASI-02)
SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Private Key blocks
    (
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
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
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "[REDACTED_JWT_TOKEN]",
    ),
    # OpenAI, Anthropic, or GitHub tokens
    (
        re.compile(r"\b(sk-[a-zA-Z0-9_-]{20,}|ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{22,})\b"),
        "[REDACTED_API_KEY]",
    ),
    # Database URIs with credentials
    (
        re.compile(r"(postgresql|postgres|mysql|mongodb|redis)://([^:\s]+):([^@\s]+)@"),
        r"\1://\2:[REDACTED_PASSWORD]@",
    ),
]


def scrub_sensitive_information(text: str, preserve_lines: bool = False) -> str:
    """
    Scrub credentials, API keys, JWTs, and private keys from untrusted document text.
    Mitigates OWASP LLM02 & ASI-02 (Sensitive Information Disclosure).

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


def generate_canary_token() -> str:
    """Generate a cryptographic per-session/per-turn UUID canary token."""
    return f"CANARY_{uuid4().hex[:12].upper()}"


def sanitize_untrusted_text(text: str) -> str:
    """
    Sanitize text retrieved from external or user-uploaded documents to prevent delimiter breakout attacks.
    Escapes any closing or opening XML-style tags that mimic untrusted_document_context.
    """
    if not text:
        return ""
    # Neutralize any attempts to prematurely close or spoof document delimiters
    sanitized = re.sub(
        r"</?untrusted_document_context[^>]*>",
        lambda m: html.escape(m.group(0)),
        text,
        flags=re.IGNORECASE,
    )
    return sanitized


def wrap_untrusted_context(
    content: str,
    filename: str = "document.md",
    start_line: int | None = None,
    end_line: int | None = None,
    doc_id: str | None = None,
) -> str:
    """
    Wrap untrusted retrieved document content with strict XML-style security boundaries.
    Instructs models to treat content within boundaries strictly as passive data, never instructions.
    """
    safe_content = sanitize_untrusted_text(content)
    line_attr = f' lines="{start_line}-{end_line}"' if start_line and end_line else ""
    doc_attr = f' id="{doc_id}"' if doc_id else ""

    return (
        f'<untrusted_document_context filename="{html.escape(filename)}"{doc_attr}{line_attr}>\n'
        f"{safe_content.strip()}\n"
        f"</untrusted_document_context>"
    )


def detect_prompt_injection(text: str) -> tuple[bool, str | None]:
    """
    Scan query or text for known adversarial prompt injection indicators.
    Returns (is_injected, matched_reason).
    """
    if not text:
        return False, None

    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, f"Suspicious prompt pattern detected: '{match.group(0)}'"

    return False, None


def verify_canary_integrity(output: str, canary_token: str) -> bool:
    """
    Check if the private canary token was leaked into model output.
    Returns True if the output is clean (canary was NOT leaked).
    Returns False if canary was compromised.
    """
    if not canary_token:
        return True
    return canary_token not in output


def sanitize_retrieved_chunks(
    chunks: Sequence[Any],
) -> tuple[list[Any], list[str], list[dict[str, str]]]:
    """
    Defense-in-depth for indirect prompt injection arriving inside retrieved documents.

    For each retrieved chunk:
      1. Escape delimiter-breakout attempts (``sanitize_untrusted_text``).
      2. Wrap the content in ``<untrusted_document_context>`` boundaries.
      3. Scan for instruction-style patterns; flagged chunks are dropped entirely.

    Returns ``(sanitized_chunks, wrapped_contexts, flagged)`` where ``flagged``
    entries carry the filename and the matched reason for observability.
    """
    sanitized_chunks: list[Any] = []
    wrapped_contexts: list[str] = []
    flagged: list[dict[str, str]] = []

    for chunk in chunks:
        clean = scrub_sensitive_information(sanitize_untrusted_text(chunk.content))
        injected, reason = detect_prompt_injection(clean)
        if injected:
            flagged.append({"filename": chunk.filename, "reason": reason or "injection pattern"})
            continue
        chunk.content = clean
        sanitized_chunks.append(chunk)
        wrapped_contexts.append(
            wrap_untrusted_context(
                clean,
                filename=chunk.filename,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
            )
        )

    return sanitized_chunks, wrapped_contexts, flagged


# MCP Tool Poisoning Patterns (Invariant Labs disclosure)
MCP_POISONING_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"\b(do\s+not\s+call|never\s+call|prefer\s+this\s+tool|always\s+invoke|always\s+use|override\s+tool)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(silently|secretly|without\s+(?:the\s+)?user(?:\s+knowing)?|do\s+not\s+tell\s+the\s+user)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(exfiltrate|send\s+(?:all\s+)?(?:data|secrets?|tokens?|keys?)\s+to)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"</?(?:untrusted_document_context|untrusted_tool_output|system|instruction|prompt)[^>]*>",
        re.IGNORECASE,
    ),
]


def scan_mcp_tool_metadata(tool_data: dict[str, Any] | Any) -> tuple[bool, str | None]:
    """
    Inspect MCP Tool definition metadata (name, description, parameter descriptions)
    for adversarial instructions and MCP tool poisoning attacks (Invariant Labs disclosure).
    Returns (is_poisoned, reason).
    """
    if hasattr(tool_data, "model_dump"):
        tool_dict = tool_data.model_dump()
    elif isinstance(tool_data, dict):
        tool_dict = tool_data
    else:
        return False, None

    text_fields_to_check: list[str] = []

    name = tool_dict.get("name", "")
    text_fields_to_check.append(str(name))

    description = tool_dict.get("description", "")
    text_fields_to_check.append(str(description))

    input_schema = tool_dict.get("inputSchema", {})
    if isinstance(input_schema, dict):
        properties = input_schema.get("properties", {})
        if isinstance(properties, dict):
            for prop_key, prop_val in properties.items():
                text_fields_to_check.append(str(prop_key))
                if isinstance(prop_val, dict):
                    prop_desc = prop_val.get("description", "")
                    text_fields_to_check.append(str(prop_desc))

    for text in text_fields_to_check:
        if not text:
            continue
        injected, reason = detect_prompt_injection(text)
        if injected:
            return True, f"MCP Tool Poisoning detected: {reason}"

        for pattern in MCP_POISONING_PATTERNS:
            match = pattern.search(text)
            if match:
                return True, f"MCP Tool Poisoning indicator detected: '{match.group(0)}'"

    return False, None


def compute_mcp_tool_hash(tool_data: dict[str, Any] | Any) -> str:
    """
    Compute a deterministic canonical SHA-256 hash of an MCP tool definition
    to detect unauthorized runtime modifications (rug pulls).
    """
    if hasattr(tool_data, "model_dump"):
        tool_dict = tool_data.model_dump()
    elif isinstance(tool_data, dict):
        tool_dict = tool_data
    else:
        tool_dict = {"raw": str(tool_data)}

    canonical_data = {
        "name": tool_dict.get("name"),
        "description": tool_dict.get("description"),
        "inputSchema": tool_dict.get("inputSchema"),
    }
    canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
