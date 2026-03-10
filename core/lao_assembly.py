"""
core/lao_assembly.py
IPA → Lao script assembly for Khmer-script languages.

Pure logic only: all data (glyph_map, coda_map, rime_maps) is passed in as
arguments.  The data itself lives in the pipeline module that uses it
(e.g. pipelines/brao_khmer_lao.py).

Assembly algorithm per syllable
────────────────────────────────
1.  Coda normalisation
      Map IPA coda to its Lao-compatible intermediate form (e.g. p→b, t→d).
      Lao writes final stops with their voiced equivalents.
      Glottal-stop coda is NOT normalised here; it is handled in step 2.

2.  Special V+F combinations  (vowel_coda_logic)
      am / aj / aw        — absorb coda consonant into a compound vowel token
      short vowel + ʔ     — fuse into glottalized vowel form (e.g. a+ʔ → aʔ)
      long vowel  + ʔ     — replace coda with 'ʔˈ' (ʔ + karan silent mark)

3.  Vowel template lookup
      Select from open_rime_map  (when F = ∅)
               or closed_rime_map (when F ≠ ∅).
      Template is a list of IPA tokens; '_' marks the onset position.
      Joined to a string, then '_' is replaced by the onset in step 5.

4.  Build IPA onset string: C + M  (medial uses the same glyph as C)

5.  Substitute '_' into template; append normalised F if F ≠ ∅
      Everything is still in IPA at this point.

6.  Presyllable (converted directly to avoid compound-token collisions)
      P     → glyph_map[P]
      R in {m n ɲ ŋ r l} → sara-a-short (ັ) + glyph_map[R]
      R = 'a'             → sara-aa (າ)

7.  Final glyph pass
      Longest-match regex substitution of the assembled IPA main-syllable
      string through glyph_map → Lao glyphs.
      Presyllable was already converted in step 6 and is prepended as-is.
"""
import re

_NULL        = "∅"
_LONG_VOWEL  = "ː"          # U+02D0 IPA length mark
_NASAL_LATERAL = {"m", "n", "ɲ", "ŋ", "r", "l"}
_SARA_A_SHORT  = "\u0eb1"   # ັ  Lao sara a (short)
_SARA_AA       = "\u0eb2"   # າ  Lao sara aa (long)


# ── Glyph-map application ─────────────────────────────────────────────────────

def _apply_glyph_map(s: str, glyph_map: dict) -> str:
    """
    Longest-match regex substitution of IPA tokens → Lao glyphs.
    Segments not found in glyph_map are passed through unchanged.
    """
    if not s:
        return s
    pattern = re.compile(
        "|".join(re.escape(k) for k in sorted(glyph_map, key=len, reverse=True))
    )
    return pattern.sub(lambda m: glyph_map[m.group(0)], s)


# ── Special vowel+coda combinations ──────────────────────────────────────────

def _vowel_coda_logic(V: str, F: str) -> tuple:
    """
    Resolve special V+F pairings before the vowel template lookup.

    Returns (V, F) with F possibly set to ∅ when absorbed into V.
    """
    # Sara -am / -aj / -aw: absorb nasal/glide into compound vowel
    if F == "m" and V == "a":
        return "am", _NULL
    if F == "j" and V == "a":
        return "aj", _NULL
    if F == "w" and V == "a":
        return "aw", _NULL

    # Glottalized rimes
    if F == "ʔ":
        if _LONG_VOWEL not in V:
            # Short vowel: fuse V+ʔ (e.g. a+ʔ → aʔ, which → sara-aʔ ะ)
            return V + "ʔ", _NULL
        else:
            # Long vowel: keep V; coda becomes ʔˈ (glottal stop + karan ໌)
            return V, "ʔˈ"

    return V, F


# ── Vowel template lookup ─────────────────────────────────────────────────────

def _get_vowel_template(V: str, F: str,
                        open_rime_map: dict, closed_rime_map: dict):
    """
    Return the joined vowel-template schematic string, or None if unrecognised.
    '_' in the template marks the onset position.
    """
    row = open_rime_map.get(V) if F == _NULL else closed_rime_map.get(V)
    if row is None:
        return None
    return "".join(row)


# ── Core assembly ─────────────────────────────────────────────────────────────

def assemble_lao_word(
    syl: dict,
    glyph_map: dict,
    coda_map: dict,
    open_rime_map: dict,
    closed_rime_map: dict,
) -> str:
    """
    Build the Lao word string from a processed IPA syllable dict.

    Returns 'ERROR' if a required vowel template or coda is not found.
    The syllable dict's IPA slots are read but not modified.
    """
    C = syl.get("C", "") or ""
    M = syl.get("M", "") or ""
    V = syl.get("V", "") or ""
    F = syl.get("F", "") or _NULL
    P = syl.get("P", "") or ""
    R = syl.get("R", "") or ""

    # Normalise explicit null-placeholders
    if C == _NULL:  C = ""
    if M == _NULL:  M = ""
    if not F or F == _NULL:  F = _NULL

    # ── 1. Coda normalisation ──────────────────────────────────────────────────
    # ʔ is left as-is here; _vowel_coda_logic handles it in step 2.
    if F != _NULL:
        F = coda_map.get(F, F)

    # ── 2. Special V+F combinations ───────────────────────────────────────────
    V, F = _vowel_coda_logic(V, F)

    # ── 3. Vowel template ─────────────────────────────────────────────────────
    template = _get_vowel_template(V, F, open_rime_map, closed_rime_map)
    if template is None:
        return "ERROR"

    # ── 4. IPA onset string ───────────────────────────────────────────────────
    onset = C + M

    # ── 5. Build IPA main-syllable string ─────────────────────────────────────
    main_ipa = template.replace("_", onset)
    if F != _NULL:
        main_ipa += F

    # ── 6. Presyllable (converted directly to avoid compound-token collisions) ─
    # e.g. "m" presyl rime: 'a'+'m' → 'am' → ຳ (sara-am) if put through glyph
    # pass, which is wrong — we want sara-a-short + ມ instead.  Convert directly.
    P_lao = ""
    R_lao = ""
    if P and P != _NULL:
        P_lao = glyph_map.get(P, P)
        if R and R != _NULL:
            if R in _NASAL_LATERAL:
                R_lao = _SARA_A_SHORT + glyph_map.get(R, R)
            elif R == "a":
                R_lao = _SARA_AA
            # Other R values are unsupported; R_lao stays ""

    # ── 7. Final glyph pass on main syllable ──────────────────────────────────
    main_lao = _apply_glyph_map(main_ipa, glyph_map)

    return P_lao + R_lao + main_lao


# ── Batch helpers ─────────────────────────────────────────────────────────────

def apply_lao_conversion(
    syllables: list,
    glyph_map: dict,
    coda_map: dict,
    open_rime_map: dict,
    closed_rime_map: dict,
) -> list:
    """
    Add 'word_lao' to each syllable dict with the assembled Lao word.
    All existing IPA slot values (P/R/C/M/V/F/T) are left unchanged.
    Error syllables are passed through without modification.
    """
    result = []
    for syl in syllables:
        syl = dict(syl)
        if not syl.get("error"):
            syl["word_lao"] = assemble_lao_word(
                syl, glyph_map, coda_map, open_rime_map, closed_rime_map
            )
        result.append(syl)
    return result


def syllables_to_lao(syllables: list) -> str:
    """Join word_lao values from processed syllable dicts."""
    return " ".join(syl["word_lao"] for syl in syllables if syl.get("word_lao"))
