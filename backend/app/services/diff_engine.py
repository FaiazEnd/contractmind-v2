"""Word-level diff tokenizer for redline comparison and OpenXML export."""
from __future__ import annotations

import difflib
import re
from typing import Any


TOKEN_SPLIT_PATTERN = re.compile(r"\S+\s*")


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return TOKEN_SPLIT_PATTERN.findall(text)


def compute_word_diff(original_text: str, suggested_text: str) -> list[dict[str, str]]:
    """Compute coalesced word-level diff tokens between original and suggested clause text."""
    orig_tokens = _tokenize(original_text)
    sugg_tokens = _tokenize(suggested_text)

    matcher = difflib.SequenceMatcher(None, orig_tokens, sugg_tokens, autojunk=False)
    raw_ops: list[dict[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            raw_ops.append({"type": "equal", "text": "".join(orig_tokens[i1:i2])})
        elif tag == "delete":
            raw_ops.append({"type": "delete", "text": "".join(orig_tokens[i1:i2])})
        elif tag == "insert":
            raw_ops.append({"type": "insert", "text": "".join(sugg_tokens[j1:j2])})
        elif tag == "replace":
            raw_ops.append({"type": "delete", "text": "".join(orig_tokens[i1:i2])})
            raw_ops.append({"type": "insert", "text": "".join(sugg_tokens[j1:j2])})

    # Coalesce adjacent tokens of the same type
    coalesced: list[dict[str, str]] = []
    for op in raw_ops:
        if not op["text"]:
            continue
        if coalesced and coalesced[-1]["type"] == op["type"]:
            coalesced[-1]["text"] += op["text"]
        else:
            coalesced.append(op)

    return coalesced
