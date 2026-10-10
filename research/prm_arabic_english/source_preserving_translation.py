"""Deterministic prose slots; the model never owns mathematical reconstruction.

This module performs no translation. Source literals, including errors, remain
byte-for-byte Python strings. Synthetic responses in tests are not corpus drafts.
"""
from dataclasses import dataclass
import re
import unicodedata

from materialize_translation_batch import PROTECTED, NUMBER

PLAN_VERSION = "prose-slots-v1"
BAD_SCRIPT = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]")
INJECTION = re.compile(r"</?think\b|<\||```|<[A-Za-z]+\d+>|\\|\$", re.I)
OPERATOR = re.compile(r"[+−±*/=<>^%÷×√]|(?<![A-Za-z])-|-(?![A-Za-z])")
WORD = re.compile(r"[A-Za-z]{2,}(?:['’-][A-Za-z]+)*")
STRUCTURE = re.compile(r"\r\n|\r|\n|(?m:^[ \t]*(?:#{1,6}[ \t]+|[-*][ \t]+|\d+[.)][ \t]+|>[ \t]*))")
# A deliberately narrow algebra grammar: prose words cannot be operands.
ATOM = r"(?:infinite|infinity|pi|[A-Za-z]{2,}(?=\()|[A-Za-z]{2,3}(?=[\d_^=+*/()<>'-])|(?<=[\d+*/=^(-])[A-Za-z]{2,3}(?![A-Za-z])|\d+(?:[,.]\d+)*(?:[eE][+-]?\d+)?|[A-Za-z](?:_\{[^{}]*\}|_[A-Za-z0-9]+)?|[A-Z]{2,}|[\u0370-\u03ff])"
LEXEME = re.compile(ATOM + r"|[+−±*/=<>^%÷×√≤≥≠≈∞(){}\[\]-]")


def additional_math(text):
    """Undelimited LaTeX, nested arguments, and unfinished source fragments."""
    pattern = re.compile(r"\\begin\{([^{}]+)\}|\\\(.*?\\\)|\\\[.*?\\\]|\\[()[\]]|\\[A-Za-z]+\*?|\\\\", re.S)
    spans, cursor = [], 0
    while (match := pattern.search(text, cursor)) is not None:
        end = match.end()
        if match[1] is not None:
            marker = "\\end{" + match[1] + "}"
            close = text.find(marker, end)
            end = close + len(marker) if close >= 0 else len(text)
        elif match.group() in ("\\(", "\\["):
            end = len(text)
        while True:
            start = end
            while start < len(text) and text[start].isspace():
                start += 1
            if start >= len(text) or text[start] != "{":
                break
            depth, pos = 1, start + 1
            while pos < len(text) and depth:
                if text[pos] in "{}" and text[pos - 1] != "\\":
                    depth += 1 if text[pos] == "{" else -1
                pos += 1
            end = len(text) if depth else pos
            if depth:
                break
        spans.append((match.start(), end, text[match.start():end]))
        cursor = end
    return spans


def bare_math(text):
    """Identify connected bare algebra without swallowing adjacent prose."""
    tokens = []
    for match in LEXEME.finditer(text):
        a, b = match.span()
        # Do not take letters/numbers from within ordinary words.
        if ((re.match(r"[A-Za-z0-9]", match[0]) and a and re.match(r"[A-Za-z_]", text[a - 1]))
                or (re.search(r"[A-Za-z0-9]$", match[0]) and b < len(text) and re.match(r"[A-Za-z]", text[b])
                    and not (match[0][-1].isdigit() and re.match(r"(?:[A-Za-z]{2,}\(|[A-Za-z]{1,3}(?![A-Za-z]))", text[b:])))):
            continue
        tokens.append(match)
    groups, current = [], []
    for token in tokens:
        if current and text[current[-1].end():token.start()].strip():
            groups.append(current)
            current = []
        current.append(token)
    if current:
        groups.append(current)
    spans = []
    for group in groups:
        a, b = group[0].start(), group[-1].end()
        value = text[a:b]
        if value.endswith("-") and b < len(text) and re.match(r"[A-Za-z]", text[b]) and len(group[0][0]) > 1:
            continue
        # An operator or variable/function with parentheses makes a formula.
        if re.search(r"[=^+−±*/<>÷×√≤≥≠≈∞]|(?<![A-Za-z])-|-(?![A-Za-z])", value) or re.search(r"[A-Za-z]\(", value):
            spans.append((a, b, value))
    return spans


def merge(spans):
    result = []
    for a, b in sorted(spans):
        if result and a <= result[-1][1]:
            result[-1] = (result[-1][0], max(b, result[-1][1]))
        else:
            result.append((a, b))
    return result


def math_spans(source):
    spans = [(m.start(), m.end()) for m in PROTECTED.finditer(source)]
    spans.extend(m.span() for m in re.finditer(r"\[\*\s*\d+\s*\]", source))
    # Environments can contain dollar-delimited cells. Freeze the outer
    # environment before scanning its gaps, including malformed source code.
    for match in re.finditer(r"\\begin\{([^{}]+)\}", source):
        if any(a <= match.start() < b for a, b in spans):
            continue
        marker = "\\end{" + match[1] + "}"
        close = source.find(marker, match.end())
        spans.append((match.start(), close + len(marker) if close >= 0 else len(source)))
    spans = merge(spans)
    # Scan only gaps: commands inside delimited mathematics must not consume
    # following prose when that equation contains an unfinished command.
    cursor = 0
    explicit = list(spans)
    for a, b in explicit + [(len(source), len(source))]:
        gap = source[cursor:a]
        spans.extend((cursor + x, cursor + y) for x, y, _ in additional_math(gap))
        cursor = b
    spans = merge(spans)
    cursor = 0
    for a, b in list(spans) + [(len(source), len(source))]:
        gap = source[cursor:a]
        spans.extend((cursor + x, cursor + y) for x, y, _ in bare_math(gap))
        spans.extend((cursor + m.start(), cursor + m.end()) for m in re.finditer(r"\d+(?:[,.]\d+)*(?:[eE][+-]?\d+)?", gap))
        # Single mathematical symbols and identifiers also matter. English
        # articles/pronouns a/A/I are prose unless inside a formula above.
        symbols = r"(?<![A-Za-z'’])[B-HJ-Zb-hj-z](?![A-Za-z'’])|(?<![A-Za-z])[A-Z]{2,}(?![A-Za-z])|[\u0370-\u03ff]|[+−±*/=<>^%÷×√_|\\{}\[\]-]"
        spans.extend((cursor + m.start(), cursor + m.end()) for m in re.finditer(symbols, gap))
        spans.extend((cursor + i, cursor + i + 1) for i, c in enumerate(gap)
                     if unicodedata.category(c) in ("Sm", "No"))
        spans.extend((cursor + m.start(), cursor + m.end()) for m in
                     re.finditer(r"(?<=,)(?:infinite|infinity)(?=[)\]])", gap))
        spans.extend((cursor + m.start(), cursor + m.end()) for m in re.finditer(r"(?<![A-Za-z])[A-Za-z]\.[A-Za-z]\.(?![A-Za-z])", gap))
        for match in re.finditer(r"[(,]\s*([aAI])(?=\s*[,)]|\s+[=+*/^-])", gap):
            spans.append((cursor + match.start(1), cursor + match.end(1)))
        for match in re.finditer(r"\b(?:variable|coefficient|root|for|let|called|denoted by|side|value of)\s+([aAI])(?=$|[.,;:)\]}=+<>/*^]|\s+(?:is|are|be|equals|and|or)\b)", gap, re.I):
            spans.append((cursor + match.start(1), cursor + match.end(1)))
        if re.search(r"[\u0600-\u06ff]", gap):
            # In an Arabic candidate these remaining Latin letters are source
            # identifiers, not the English article/pronoun translated away.
            spans.extend((cursor + m.start(), cursor + m.end())
                         for m in re.finditer(r"(?<![A-Za-z'’])[aAI](?![A-Za-z'’])", gap))
        # An unmatched source dollar delimiter is an error to preserve, never
        # an invitation to close it or rewrite the remaining expression.
        dollar = gap.find("$")
        if dollar >= 0:
            spans.append((cursor + dollar, a))
        cursor = b
    return merge(spans)


@dataclass(frozen=True)
class Piece:
    text: str
    slot: str | None = None


def plan(source):
    """Return literal/prose pieces; joining their text recreates the source."""
    spans = merge(math_spans(source) + [m.span() for m in STRUCTURE.finditer(source)])
    pieces, cursor, next_slot = [], 0, 0

    def prose(gap):
        nonlocal next_slot
        # Bound individual prose inputs. Split only at existing spaces; do
        # not manufacture punctuation or new paragraph/step boundaries.
        while gap:
            leading = re.match(r"[^A-Za-z]*", gap)[0]
            if leading:
                pieces.append(Piece(leading))
                gap = gap[len(leading):]
                if not gap:
                    return
            end = len(gap)
            if end > 400:
                split = gap.rfind(" ", 0, 401)
                if split > 0:
                    end = split
            chunk, gap = gap[:end], gap[end:]
            body = re.sub(r"[^A-Za-z]*$", "", chunk)
            trailing = chunk[len(body):]
            if WORD.search(body):
                pieces.append(Piece(body, f"s{next_slot}"))
                next_slot += 1
            elif body:
                pieces.append(Piece(body))
            if trailing:
                pieces.append(Piece(trailing))

    for a, b in spans:
        prose(source[cursor:a])
        pieces.append(Piece(source[a:b]))
        cursor = b
    prose(source[cursor:])
    if "".join(p.text for p in pieces) != source:
        raise ValueError("Internal source partition mismatch")
    return pieces


def slots_for(source):
    return {p.slot: p.text for p in plan(source) if p.slot is not None}


def validate_slot(source, draft):
    if not isinstance(draft, str) or not draft.strip() or draft != draft.strip():
        raise ValueError("Empty prose slot or added boundary whitespace")
    if (NUMBER.search(draft) or OPERATOR.search(draft) or INJECTION.search(draft)
            or re.search(r"[\u0370-\u03ff]", draft)
            or any(unicodedata.category(c) in ("Sm", "No") for c in draft)):
        raise ValueError("Generated mathematical content/placeholder in prose slot")
    if (BAD_SCRIPT.search(draft) or any(unicodedata.category(c) in ("Cc", "Cf") for c in draft)
            or any(c.isalpha() and "ARABIC" not in unicodedata.name(c, "") for c in draft)
            or any(unicodedata.category(c).startswith("N") for c in draft)):
        raise ValueError("Unexpected script or control/line boundary in prose slot")
    if re.search(r"^\s*(?:#|[-*]|>|(?:step|الخطوة|خطوة)\s*\d)", draft, re.I):
        raise ValueError("Generated reasoning/header/list boundary in prose slot")
    arabic = sum(c.isalpha() and "ARABIC" in unicodedata.name(c, "") for c in draft)
    latin = len(re.findall(r"[A-Za-z]", draft))
    if not arabic or arabic < latin:
        raise ValueError("Arabic prose missing or dominated by untranslated Latin text")
    # Latin identifiers cannot be introduced or reordered as disguised math.
    if re.findall(r"\b[A-Za-z]+\b", draft):
        raise ValueError("Untranslated Latin text/identifier in prose slot")
    # Reject residual markup and punctuation used to wrap mathematical output.
    if re.search(r"[\[\]{}|`#]", draft):
        raise ValueError("Generated markup in prose slot")
    return draft


def assemble(source, translations):
    pieces = plan(source)
    expected = {p.slot for p in pieces if p.slot is not None}
    if set(translations) != expected:
        raise ValueError("Prose slot coverage mismatch")
    return "".join(p.text if p.slot is None else validate_slot(p.text, translations[p.slot]) for p in pieces)


def fingerprint(source):
    """Ordered exact math literals, independent of translated prose."""
    return [source[a:b] for a, b in math_spans(source)]


def validate_math(source, translated):
    # Align against source-owned literals rather than interpreting Arabic
    # neighborhoods using English lexer rules. A translated word beside x or
    # a numeric literal must not change whether that source literal is math.
    literals = fingerprint(source)
    pattern = "(.*?)" + "(.*?)".join(re.escape(value) for value in literals) + ("(.*?)" if literals else "")
    match = re.fullmatch(pattern, translated, re.S)
    if match is None:
        raise ValueError("Exact mathematical expressions/identifiers or numeric order changed")
    for gap in match.groups():
        if (NUMBER.search(gap) or INJECTION.search(gap) or OPERATOR.search(gap)
                or re.search(r"[\u0370-\u03ff]|[{}\[\]]", gap)
                or any(letter not in re.findall(r"(?<![A-Za-z])[A-Za-z](?![A-Za-z])", source)
                       for letter in re.findall(r"(?<![A-Za-z])[A-Za-z](?![A-Za-z])", gap))
                or any(unicodedata.category(c) in ("Sm", "No") for c in gap)):
            raise ValueError("Additional mathematical content outside exact source literals")
    return translated
