"""
Post-generation guardrails for the RAG pipeline.

Validates LLM output against canonical book data to catch:
- Hallucinated titles not in the candidate set
- Wrong author attributions
- Mentioned book IDs that don't exist

If validation fails, provides a repair prompt for one retry.
"""

import re
from typing import Optional

from app.rag.schemas import BookCandidate


def validate_response(
    text: str,
    candidates: list[BookCandidate],
) -> tuple[bool, list[str]]:
    """
    Validate LLM response against canonical candidate data.

    Checks:
      1. Every **bolded title** or [ID:X] in the response exists in candidates
      2. Author names paired with titles match canonical records
      3. No hallucinated IDs

    Returns:
        (is_valid, list_of_error_strings)
    """
    errors: list[str] = []
    if not candidates or not text:
        return True, []

    # Build lookup maps
    id_set = {c.id for c in candidates}
    title_lower_map = {c.title.lower(): c for c in candidates}  # title → candidate
    # Also map first significant words for fuzzy matching
    title_word_map: dict[str, BookCandidate] = {}
    for c in candidates:
        # Use first 3 significant words as a key
        words = [w for w in c.title.lower().split() if w not in ("the", "a", "an", "of", "and")]
        if words:
            key = " ".join(words[:3])
            title_word_map[key] = c

    # ── Check 1: Bolded titles exist in candidates ──
    # Pattern: **Title** or **Title** by Author
    bold_titles = re.findall(r'\*\*(.+?)\*\*', text)
    for bold in bold_titles:
        # Skip section headers (e.g. "Pacing & Tone:", "Best For:")
        if bold.rstrip().endswith(':'):
            continue

        # Strip "by Author" if present
        title_part = re.sub(r'\s+by\s+.+$', '', bold, flags=re.IGNORECASE).strip()
        title_lower = title_part.lower()

        # Exact match
        if title_lower in title_lower_map:
            # Check author if "by Author" is in the bold text
            author_match = re.search(r'by\s+(.+)$', bold, re.IGNORECASE)
            if author_match:
                stated_author = author_match.group(1).strip().lower()
                canonical = title_lower_map[title_lower]
                if stated_author not in canonical.author.lower():
                    errors.append(
                        f"Wrong author: '{bold}' — canonical author is '{canonical.author}'"
                    )
            continue

        # Fuzzy: check if title is a substring of any candidate
        found = False
        for ct_lower, c in title_lower_map.items():
            if title_lower in ct_lower or ct_lower in title_lower:
                found = True
                break
        if not found:
            # Check word-based fuzzy
            words = [w for w in title_lower.split() if w not in ("the", "a", "an", "of", "and")]
            key = " ".join(words[:3])
            if key not in title_word_map and len(title_lower) > 5:
                errors.append(f"Hallucinated title: '**{title_part}**' not in candidates")

    # ── Check 2: Referenced IDs exist ──
    id_refs = re.findall(r'\[ID:(\d+)\]', text)
    for id_str in id_refs:
        ref_id = int(id_str)
        if ref_id not in id_set:
            errors.append(f"Hallucinated ID: [ID:{ref_id}] not in candidate set")

    return len(errors) == 0, errors


def build_repair_prompt(
    original_query: str,
    errors: list[str],
    candidates: list[BookCandidate],
) -> str:
    """
    Build a strict repair prompt that fixes specific validation errors.

    Used for one retry when validate_response fails.
    """
    error_list = "\n".join(f"- {e}" for e in errors)

    candidate_titles = "\n".join(
        f"- \"{c.title}\" by {c.author} [ID:{c.id}]"
        for c in candidates
    )

    return f"""Your previous response had factual errors:

{error_list}

The ONLY books you may reference are:
{candidate_titles}

Please answer the original question again using ONLY these books.
Do NOT invent any titles or authors. Match titles and authors EXACTLY.

Original question: {original_query}"""
