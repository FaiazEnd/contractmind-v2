"""Word-level diff token engine for redline visualization and OpenXML Track Changes."""

from __future__ import annotations

import difflib
import re
from typing import Dict, List

_TOKEN_RE = re.compile(r"\S+\s*")


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return _TOKEN_RE.findall(text)


def compute_word_diff(original_text: str, suggested_text: str) -> List[Dict[str, str]]:
    """Compute word-level diff tokens of type 'equal', 'del', or 'ins'."""
    orig_tokens = _tokenize(original_text)
    sugg_tokens = _tokenize(suggested_text)

    matcher = difflib.SequenceMatcher(None, orig_tokens, sugg_tokens, autojunk=False)
    diff_tokens: List[Dict[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            chunk = "".join(orig_tokens[i1:i2])
            if chunk:
                diff_tokens.append({"type": "equal", "text": chunk})
        elif tag == "delete":
            chunk = "".join(orig_tokens[i1:i2])
            if chunk:
                diff_tokens.append({"type": "del", "text": chunk})
        elif tag == "insert":
            chunk = "".join(sugg_tokens[j1:j2])
            if chunk:
                diff_tokens.append({"type": "ins", "text": chunk})
        elif tag == "replace":
            del_chunk = "".join(orig_tokens[i1:i2])
            ins_chunk = "".join(sugg_tokens[j1:j2])
            if del_chunk:
                diff_tokens.append({"type": "del", "text": del_chunk})
            if ins_chunk:
                diff_tokens.append({"type": "ins", "text": ins_chunk})

    return diff_tokens
