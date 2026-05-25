from __future__ import annotations

import html
import json
import re
import unicodedata
from typing import Any, Dict, List, Sequence

REQUIRED_SECTIONS = [
    "Executive Overview",
    "Key Completed Work",
    "Ongoing / In Progress",
    "Pending / Risks",
]

# Characters that commonly break ReportLab/older PDF fonts or appear as black boxes.
_DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u00ad"
_SPACE_CHARS = "\u00a0\u2007\u202f"
_BAD_TO_ASCII = {
    ord(ch): "-" for ch in _DASH_CHARS
} | {
    ord(ch): " " for ch in _SPACE_CHARS
} | {
    ord("\u25a0"): "-",  # black square fallback
    ord("\ufffd"): "",   # replacement character
    ord("\u2022"): "•",
}


def normalize_text(value: Any) -> str:
    """Normalize model/Excel text before saving or rendering PDF."""
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_BAD_TO_ASCII)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove markdown emphasis that should never be visible in the PDF.
    text = re.sub(r"(?<!\*)\*\*(?!\*)", "", text)
    text = re.sub(r"(?<!\*)\*(?!\*)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_code_fences(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"^```(?:json|text|markdown)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_json_object(text: str) -> Dict[str, Any]:
    """Parse the first JSON object from a model response."""
    cleaned = strip_code_fences(text)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Robust fallback: find the largest likely JSON object region.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        candidate = cleaned[start : end + 1]
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj
    raise ValueError("Model did not return a valid JSON object.")


def _coerce_bullets(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        # Allow emergency recovery from strings containing bullet lines.
        parts = [x.strip() for x in re.split(r"\n+", value) if x.strip()]
        items = parts
    else:
        items = [str(value)]

    bullets: List[str] = []
    for item in items:
        line = normalize_text(item)
        line = re.sub(r"^[\-•*\d.)\s]+", "", line).strip()
        if line:
            bullets.append(line)
    return bullets


def validate_sections(obj: Dict[str, Any], required: Sequence[str] | None = None) -> Dict[str, List[str]]:
    """Return a normalized section dict with all required sections present."""
    required = list(required or REQUIRED_SECTIONS)
    normalized: Dict[str, List[str]] = {}
    # Accept case/space/colon variants from the model.
    lookup = {normalize_text(k).strip().lower().rstrip(":"): v for k, v in obj.items()}
    for section in required:
        key = section.lower()
        value = lookup.get(key)
        bullets = _coerce_bullets(value)
        normalized[section] = bullets or ["No major items identified."]
    return normalized


def sections_to_text(sections: Dict[str, Sequence[str]], required: Sequence[str] | None = None) -> str:
    """Serialize structured sections to plain text for Excel storage."""
    required = list(required or REQUIRED_SECTIONS)
    lines: List[str] = []
    for section in required:
        lines.append(section)
        for bullet in sections.get(section, []) or ["No major items identified."]:
            lines.append(f"- {normalize_text(bullet)}")
        lines.append("")
    return "\n".join(lines).strip()


def parse_sections_from_text(text: str, required: Sequence[str] | None = None) -> Dict[str, List[str]]:
    """Parse stored plain text back into sections for PDF rendering."""
    required = list(required or REQUIRED_SECTIONS)
    text = normalize_text(text)
    heading_pattern = re.compile(
        r"^(" + "|".join(re.escape(s) for s in sorted(required, key=len, reverse=True)) + r")\s*:?\s*$",
        flags=re.IGNORECASE,
    )
    current: str | None = None
    data: Dict[str, List[str]] = {s: [] for s in required}
    canonical = {s.lower(): s for s in required}

    for raw_line in text.splitlines():
        line = normalize_text(raw_line)
        if not line:
            continue
        match = heading_pattern.match(line)
        if match:
            current = canonical[match.group(1).lower()]
            continue
        if current is None:
            # Ignore stray text such as "Summary" instead of rendering it.
            continue
        line = re.sub(r"^[\-•*]\s*", "", line).strip()
        if line:
            data[current].append(line)

    return validate_sections(data, required)


def esc(value: Any) -> str:
    return html.escape(normalize_text(value))
