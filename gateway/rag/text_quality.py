import re
import unicodedata

_URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9'/-]*")
_REPEAT_PATTERN = re.compile(r"(..)\1{6,}")
_ARTIFACT_PATTERNS = (
    re.compile(r"\b(?:obj|endobj|stream|endstream|xref|startxref)\b", re.IGNORECASE),
    re.compile(
        r"/(?:Type|Filter|Length|MediaBox|Parent|Contents|Resources|ProcSet|FontDescriptor|"
        r"XObject|ColorSpace|BitsPerComponent|Subtype|Kids|Annots)\b"
    ),
    re.compile(r"\b(?:documentid=|cidinit|begincmap|endcmap|%%eof)\b", re.IGNORECASE),
    re.compile(r"\.(?:jpg|jpeg|png|gif|bmp|svg|tiff)\b", re.IGNORECASE),
)


def normalize_text(text: str) -> str:
    """Normalize control characters and line endings while preserving paragraphs."""
    if not text:
        return ""

    normalized = unicodedata.normalize("NFKC", text).replace("\x00", " ")
    characters: list[str] = []
    for char in normalized:
        if char in "\n\r\t":
            characters.append(char)
            continue
        if unicodedata.category(char).startswith("C"):
            characters.append(" ")
            continue
        characters.append(char)

    return "".join(characters).replace("\r\n", "\n").replace("\r", "\n")


def make_text_fingerprint(text: str, token_limit: int = 30) -> str:
    """Build a lightweight content fingerprint for dedupe."""
    tokens = re.findall(r"[a-z0-9]{2,}", text.lower())
    return " ".join(tokens[:token_limit])


def truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text.strip()

    truncated = text[:max_chars].rsplit(" ", 1)[0].strip()
    return truncated or text[:max_chars].strip()


def score_text_quality(text: str) -> float:
    """Score text by how much it looks like natural-language ESG content."""
    lines = [_collapse_spaces(line) for line in normalize_text(text).split("\n")]
    scored_lines = [line for line in lines if line]
    if not scored_lines:
        return 0.0

    total_weight = 0
    weighted_score = 0.0
    for line in scored_lines[:40]:
        weight = min(len(line), 400)
        weighted_score += _score_line_quality(line) * weight
        total_weight += weight

    return round(weighted_score / max(total_weight, 1), 4)


def clean_document_text(text: str, min_line_score: float = 0.24) -> str:
    """Strip common PDF extraction artifacts while keeping useful ESG prose."""
    normalized = normalize_text(text)
    if not normalized.strip():
        return ""

    kept_lines: list[str] = []
    fallback_lines: list[str] = []
    seen_fingerprints: set[str] = set()

    for raw_line in normalized.split("\n"):
        line = _collapse_spaces(raw_line)
        if not line:
            continue

        score = _score_line_quality(line)
        if score < min_line_score:
            if score >= 0.12 and not _looks_like_artifact_line(line):
                fallback_lines.append(line)
            continue

        fingerprint = make_text_fingerprint(line)
        if fingerprint and fingerprint in seen_fingerprints:
            continue
        if fingerprint:
            seen_fingerprints.add(fingerprint)
        kept_lines.append(line)

    if not kept_lines:
        kept_lines = fallback_lines[:8]

    cleaned = "\n".join(kept_lines).strip()
    if cleaned:
        return cleaned

    return _collapse_spaces(normalized)


def _score_line_quality(line: str) -> float:
    if not line:
        return 0.0
    if _looks_like_artifact_line(line):
        return 0.0

    length = len(line)
    letters = sum(char.isalpha() for char in line)
    digits = sum(char.isdigit() for char in line)
    spaces = sum(char.isspace() for char in line)
    symbols = sum(not char.isalnum() and not char.isspace() for char in line)
    url_chars = sum(len(match.group(0)) for match in _URL_PATTERN.finditer(line))
    word_count = len(_WORD_PATTERN.findall(line))

    score = 0.0

    if length >= 40:
        score += 0.25
    elif length >= 20:
        score += 0.18
    elif length >= 8:
        score += 0.08

    letter_ratio = letters / max(length, 1)
    if letter_ratio >= 0.55:
        score += 0.35
    elif letter_ratio >= 0.35:
        score += 0.25
    elif letter_ratio >= 0.20:
        score += 0.10

    if word_count >= 8:
        score += 0.25
    elif word_count >= 4:
        score += 0.15
    elif word_count >= 2:
        score += 0.05

    symbol_ratio = symbols / max(length, 1)
    if symbol_ratio <= 0.15:
        score += 0.12
    elif symbol_ratio <= 0.30:
        score += 0.05
    else:
        score -= 0.12

    if url_chars:
        score -= min(0.25, url_chars / max(length, 1))
    if digits and letters:
        score += 0.05
    if spaces == 0 and length > 24:
        score -= 0.20
    if _REPEAT_PATTERN.search(line):
        score -= 0.10

    return max(0.0, min(1.0, round(score, 4)))


def _looks_like_artifact_line(line: str) -> bool:
    lower = line.lower()
    if any(pattern.search(line) for pattern in _ARTIFACT_PATTERNS):
        return True
    if _URL_PATTERN.fullmatch(line):
        return True
    if sum(len(match.group(0)) for match in _URL_PATTERN.finditer(line)) / max(len(line), 1) > 0.45:
        return True
    if len(line) > 64 and " " not in line:
        return True
    if lower.count("/") >= 5 and " " not in lower:
        return True
    if sum(char in "{}[]<>=_|\\/" for char in line) / max(len(line), 1) > 0.18:
        return True
    return False


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
