"""
Content sanitizer — strips prompt-injection patterns from ingested content.

This module is the first line of defense against **indirect prompt injection**:
malicious instructions hidden inside documents, images (EXIF / OCR), audio
transcripts, or PDFs that the system processes and eventually feeds to an LLM.

Usage::

    from app.services.processing.content_sanitizer import (
        sanitize_ingested_text,
        looks_like_injection,
    )

    clean = sanitize_ingested_text(raw_ocr_text, source="ocr")
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ============================================================================
# Injection-detection patterns
# ============================================================================

# Each tuple is (compiled_regex, human-readable description).
_INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    # --- Direct instruction override attempts ---
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I),
     "ignore previous instructions"),
    (re.compile(r"disregard\s+(all\s+)?(previous|above|prior)\s+(instructions?|context|rules)", re.I),
     "disregard previous instructions"),
    (re.compile(r"forget\s+(everything|all|your)\s+(above|previous|prior)", re.I),
     "forget previous context"),
    (re.compile(r"override\s+(previous|system|all)", re.I),
     "override instructions"),
    (re.compile(r"new\s+instructions?\s*:", re.I),
     "new instructions block"),

    # --- Role / identity hijacking ---
    (re.compile(r"you\s+are\s+now\s+(a|an|the)\b", re.I),
     "role reassignment"),
    (re.compile(r"act\s+as\s+(a|an|if\s+you)", re.I),
     "act-as prompt"),
    (re.compile(r"pretend\s+(you\s+are|to\s+be)", re.I),
     "pretend-to-be prompt"),
    (re.compile(r"from\s+now\s+on[,\s]+(you|respond|act|behave)", re.I),
     "from-now-on hijack"),

    # --- Chat-markup / template injection ---
    (re.compile(r"system\s*:\s*", re.I),
     "system: role marker"),
    (re.compile(r"<\s*/?\s*system\s*>", re.I),
     "<system> tag"),
    (re.compile(r"ASSISTANT\s*:", re.I),
     "ASSISTANT: role marker"),
    (re.compile(r"###\s*(instruction|system|prompt)", re.I),
     "### instruction header"),
    (re.compile(r"\[INST\]", re.I),
     "[INST] marker"),
    (re.compile(r"<\|im_start\|>", re.I),
     "<|im_start|> marker"),
    (re.compile(r"<\|/?(user|assistant|system)\|?>", re.I),
     "chat template marker"),
    (re.compile(r"\[/?SYS(TEM)?\]", re.I),
     "[SYS] / [SYSTEM] marker"),

    # --- Exfiltration / tool-abuse attempts ---
    (re.compile(r"(output|print|echo|return|reveal)\s+(the\s+)?(system\s+prompt|instructions|api\s+key|secret)", re.I),
     "exfiltration attempt"),
    (re.compile(r"repeat\s+(the\s+)?(above|system|initial)\s+(text|prompt|instructions?|message)", re.I),
     "repeat-system-prompt attempt"),

    # --- Delimiter / fence-breaking ---
    (re.compile(r"-{5,}"),
     "long dash delimiter (fence break attempt)"),
    (re.compile(r"={5,}"),
     "long equals delimiter (fence break attempt)"),
]

# Replacement token inserted when a pattern is stripped
_REPLACEMENT = "[FILTERED]"


# ============================================================================
# Public API
# ============================================================================


def sanitize_ingested_text(text: str, *, source: str = "") -> str:
    """
    Remove or neutralise prompt-injection patterns in ingested content.

    This should be called on **every** piece of text that enters the system
    from an external source (file content, OCR, transcripts, EXIF values,
    captions, etc.) before it is stored or embedded.

    Args:
        text:   Raw text to sanitise.
        source: An optional label for logging (e.g. ``"ocr"``, ``"exif"``).

    Returns:
        Sanitised text with injection patterns replaced by ``[FILTERED]``.
    """
    if not text:
        return text

    dirty = False
    for pattern, description in _INJECTION_PATTERNS:
        if pattern.search(text):
            if not dirty:
                logger.warning(
                    "Prompt-injection pattern detected in %s content: %s",
                    source or "unknown",
                    description,
                )
            dirty = True
            text = pattern.sub(_REPLACEMENT, text)

    return text


def looks_like_injection(text: str) -> bool:
    """
    Return ``True`` if *text* contains at least one prompt-injection pattern.

    This is a read-only check — the text is **not** modified.
    Useful for flagging content for review without altering it.
    """
    if not text:
        return False
    return any(pattern.search(text) for pattern, _ in _INJECTION_PATTERNS)


def sanitize_metadata_value(value: str, *, max_length: int = 200) -> str:
    """
    Sanitise a single metadata string (e.g. an EXIF tag value).

    Applies injection filtering **and** length-limits the result.
    """
    if not value:
        return value
    value = sanitize_ingested_text(value, source="metadata")
    if len(value) > max_length:
        value = value[:max_length]
    return value
