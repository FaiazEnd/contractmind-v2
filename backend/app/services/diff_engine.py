"""Word-level diff token computation and consensus text application engine."""

from __future__ import annotations

import difflib
import re
from typing import Any


_WORD_SPLIT_RE = re.compile(r"\S+\s*")


def compute_diff_tokens(original_text: str, suggested_text: str) -> list[dict[str, str]]:
    """Compute word-level diff tokens preserving whitespace for UI and OpenXML Track Changes."""
    orig_tokens = _WORD_SPLIT_RE.findall(original_text or "")
    sugg_tokens = _WORD_SPLIT_RE.findall(suggested_text or "")

    matcher = difflib.SequenceMatcher(None, orig_tokens, sugg_tokens, autojunk=False)
    diff_tokens: list[dict[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            chunk = "".join(orig_tokens[i1:i2])
            if chunk:
                diff_tokens.append({"type": "equal", "text": chunk})
        elif tag in ("delete", "replace"):
            del_chunk = "".join(orig_tokens[i1:i2])
            if del_chunk:
                diff_tokens.append({"type": "del", "text": del_chunk})
            if tag == "replace":
                ins_chunk = "".join(sugg_tokens[j1:j2])
                if ins_chunk:
                    diff_tokens.append({"type": "ins", "text": ins_chunk})
        elif tag == "insert":
            ins_chunk = "".join(sugg_tokens[j1:j2])
            if ins_chunk:
                diff_tokens.append({"type": "ins", "text": ins_chunk})

    return diff_tokens


def apply_redlines_to_text(
    sections: list[dict[str, Any]],
    redlines: list[dict[str, Any]],
    accepted_only: bool = True,
) -> list[dict[str, Any]]:
    """Return section copies with applicable redlines substituted into section text."""
    updated_sections: list[dict[str, Any]] = []
    for sec in sections:
        sec_copy = dict(sec)
        sec_num = str(sec_copy.get("section_number", ""))
        text = sec_copy.get("text", "")
        for redline in redlines:
            if accepted_only and redline.get("accepted") is not True:
                continue
            if not accepted_only and redline.get("accepted") is False:
                continue
            orig = redline.get("original_text", "")
            sugg = redline.get("suggested_text", "")
            if orig and sugg and (str(redline.get("section_number", "")) == sec_num or orig in text):
                if orig in text:
                    text = text.replace(orig, sugg, 1)
        sec_copy["text"] = text
        updated_sections.append(sec_copy)
    return updated_sections
