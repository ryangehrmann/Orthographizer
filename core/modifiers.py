"""
core/modifiers.py
Post-parse consonant modifier processing for Khmer → IPA transcription.

Applies four transformations to syllable dicts (P/R/C/M/V/F/T) returned by
parse_syllables(), in order:

  1. S modifier  — capital "S" in F: strip S, shorten vowel (remove ː from V)
  2. T modifier  — capital "T" in P/R/C/M: strip T, flip ¹ → ² in that cell
  3. W modifier  — capital "W" in P/R/C/M: strip W, flip ² → ¹ in that cell
  4. Tone        — determine T from the (now-modified) ¹/² in P and C, then
                   strip all ¹/² from P, R, C, M, F

These rules apply to every Khmer → IPA pipeline regardless of language module.
"""

# IPA characters treated as sonorants for tone determination
_SONORANTS = set("mnɲŋrljwh")

# ¹ = U+00B9 (SUPERSCRIPT ONE), ² = U+00B2 (SUPERSCRIPT TWO)
_NUM1 = "\u00b9"  # ¹
_NUM2 = "\u00b2"  # ²
# ː = U+02D0 (MODIFIER LETTER TRIANGULAR COLON — long-vowel marker)
_LONG_VOWEL = "\u02d0"  # ː


def _extract_numeral(s: str) -> str:
    """Return '¹' or '²' if found in *s*, else ''."""
    if _NUM1 in s:
        return _NUM1
    if _NUM2 in s:
        return _NUM2
    return ""


def _strip_numerals(s: str) -> str:
    """Remove all ¹ and ² characters from *s*."""
    return s.replace(_NUM1, "").replace(_NUM2, "")


def apply_consonant_modifiers(syllables: list, f_subs: dict | None = None) -> list:
    """
    Apply S/T/W consonant modifiers and determine the tone column (T) for
    each syllable dict.

    Args:
        syllables: list of dicts as returned by parse_syllables(); each has
                   keys P, R, C, M, V, F, T (and ambiguous, error, segments).
        f_subs:    Optional dict of exact F-column substitutions applied after
                   the S modifier but before numeral stripping.  Use this for
                   language-specific coda realisations, e.g. {"k²": "ʔ"}.

    Returns:
        A new list of dicts with cleaned P/R/C/M/F columns and T set to '¹'
        or '²' (empty string if no numeral is present).
    """
    result = []

    for syl in syllables:
        syl = dict(syl)  # shallow copy — don't mutate the original

        # ── 1. S modifier ────────────────────────────────────────────────────
        # Capital "S" in F → remove S from F; remove ː from V
        f_val = syl.get("F", "")
        if "S" in f_val:
            syl["F"] = f_val.replace("S", "")
            syl["V"] = syl.get("V", "").replace(_LONG_VOWEL, "")

        # ── 2. T modifier ────────────────────────────────────────────────────
        # Capital "T" in P/R/C/M → remove T; flip ¹ → ² in the same cell
        for col in ("P", "R", "C", "M"):
            val = syl.get(col, "")
            if "T" in val:
                val = val.replace("T", "").replace(_NUM1, _NUM2)
                syl[col] = val

        # ── 3. W modifier ────────────────────────────────────────────────────
        # Capital "W" in P/R/C/M → remove W; flip ² → ¹ in the same cell
        for col in ("P", "R", "C", "M"):
            val = syl.get(col, "")
            if "W" in val:
                val = val.replace("W", "").replace(_NUM2, _NUM1)
                syl[col] = val

        # ── 4. Language-specific F substitutions (before numeral strip) ─────
        if f_subs:
            f_val = syl.get("F", "")
            syl["F"] = f_subs.get(f_val, f_val)

        # ── 5. Tone determination ────────────────────────────────────────────
        p_val = syl.get("P", "")
        c_val = syl.get("C", "")
        p_num = _extract_numeral(p_val)
        c_num = _extract_numeral(c_val)

        if not p_val:
            # No presyllable — tone driven by main onset class
            tone = c_num
        elif p_num == c_num:
            # Both agree — use that numeral
            tone = p_num
        else:
            # Disagreement: sonorant main onset → presyllable wins; else main wins
            c_bare = _strip_numerals(c_val)
            if any(ch in c_bare for ch in _SONORANTS):
                tone = p_num
            else:
                tone = c_num

        syl["T"] = tone

        # ── 6. Strip all ¹/² from P, R, C, M, F ────────────────────────────
        for col in ("P", "R", "C", "M", "F"):
            syl[col] = _strip_numerals(syl.get(col, ""))

        result.append(syl)

    return result


def apply_vowel_allophony(syllables: list, allophony: dict) -> list:
    """
    Update the V slot of each syllable dict based on the consonant class in T.

    Looks up syl["V"] in the allophony table and replaces it with the
    class-appropriate realization (class1 for T=¹, class2 for T=²).
    Syllables whose V value is not in the table, or whose T is empty, are
    left unchanged.

    Args:
        syllables:  List of syllable dicts as returned by apply_consonant_modifiers().
        allophony:  Dict of the form {vowel: {"¹": class1_val, "²": class2_val}},
                    as returned by load_allophony().

    Returns:
        A new list of dicts with updated V values.
    """
    if not allophony:
        return syllables
    result = []
    for syl in syllables:
        syl = dict(syl)
        v = syl.get("V", "")
        t = syl.get("T", "")
        if v in allophony and t in allophony[v]:
            syl["V"] = allophony[v][t]
        syl["T"] = _strip_numerals(syl.get("T", ""))
        result.append(syl)
    return result


def syllables_to_word(syllables: list) -> str:
    """
    Reconstruct a readable IPA word string from processed syllable dicts.

    Concatenates P+R+C+M+V+F+T for each syllable (replacing the null
    placeholder '∅' with an empty string), then joins multiple syllables
    with a space.  Error syllables use their 'error' field verbatim.

    This is used by the text output processor, which needs a clean IPA
    string after consonant modifiers have been applied.
    """
    parts = []
    for syl in syllables:
        if syl.get("error"):
            parts.append(syl["error"])
        else:
            word = "".join(
                (syl.get(col, "") or "").replace("∅", "")
                for col in ("P", "R", "C", "M", "V", "F", "T")
            )
            if word:
                parts.append(word)
    return " ".join(parts)
