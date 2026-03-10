"""
pipelines/brao_khmer_ipa.py
Pipeline: Brao (Khmer script) → IPA

Self-contained: all character mappings are embedded in this module.
No external data files required.
"""
import re
from core.parsing import define_segments, parse_syllables
from core.modifiers import apply_consonant_modifiers, apply_vowel_allophony


# ── Brao Khmer → IPA conversion table ────────────────────────────────────────
# Keys: Khmer orthography strings. Values: IPA strings with class numerals ¹/².
# Longer keys are matched first during conversion (longest-match regex).
#
# Categories:
#   onsets          — consonants valid in onset position (P and C slots);
#                     includes both onset-only and dual-role (consonant_final) chars
#   codas           — consonants valid in coda position (F slot)
#   vowels          — vowel diacritics (Brao compound forms listed first so the
#                     longest-match regex picks them up before their components)
#   onset_modifiers — diacritics that modify consonant class or form clusters
#   coda_modifiers  — diacritics that modify the syllable final
#   punctuation     — punctuation marks
#   numerals        — digit characters (ASCII and Khmer)

_CONV_DICT = {
    "onsets": {
        # ── dual-role consonants (also valid as codas) ────────────────────────
        "ក": "k¹",
        "ង": "ŋ²",
        "ច": "c¹",
        "ញ": "ɲ²",
        "ត": "t¹",
        "ន": "n²",
        "ប": "b¹",
        "ម": "m²",
        "យ": "j²",
        "រ": "r²",
        "ល": "l²",
        "វ": "w²",
        # ── onset-only consonants ─────────────────────────────────────────────
        "ខ": "kʰ¹",
        "គ": "k²",
        "ឃ": "kʰ²",
        "ង៉": "ŋ¹",
        "ឆ": "ɟ¹",       # Brao: overrides standard Khmer cʰ¹
        "ជ": "c²",
        "ឈ": "ɟ²",       # Brao: overrides standard Khmer cʰ²
        "ញ៉": "ɲ¹",
        "ដ": "d¹",
        "ឋ": "ɗ¹",       # Brao: overrides standard Khmer tʰ¹
        "ឌ": "d²",
        "ឍ": "ɗ²",       # Brao: overrides standard Khmer tʰ²
        "ណ": "n¹",
        "ថ": "tʰ¹",
        "ទ": "t²",
        "ធ": "tʰ²",
        "ន៉": "n¹",
        "ប៊": "b²",
        "ប៉": "p¹",      # Brao addition
        "ផ": "pʰ¹",
        "ព": "p²",
        "ភ": "pʰ²",
        "ម៉": "m¹",
        "យ៉": "j¹",
        "រ៉": "r¹",
        "វ៉": "w¹",
        "ស": "s¹",
        "ស៊": "s²",
        "ហ": "h¹",
        "ហ៊": "h²",
        "ឡ": "l¹",
        "អ": "ʔ¹",
        "អ៊": "ʔ²",
        "អយ": "ʄ¹",
        "អ្យ": "ʄ¹",    # Brao addition: subscript-y form
        "អ៊យ": "ʄ²",
        "អ៊្យ": "ʄ²",   # Brao addition: subscript-y form
        "ឞ": "ɓ¹",      # Brao addition
        "ឞ៊": "ɓ²",     # Brao addition
        "ឝ": "g²",      # Brao addition
        "ឝ៉": "g¹",     # Brao addition
    },
    "codas": {
        "ក": "k¹",
        "ង": "ŋ²",
        "ច": "c¹",
        "ញ": "ɲ²",
        "ត": "t¹",
        "ន": "n²",
        "ប": "b¹",
        "ម": "m²",
        "យ": "j²",
        "រ": "r²",
        "ល": "l²",
        "វ": "w²",
        "គ": "k²",      # Brao addition
    },
    "vowels": {
        # Brao compound forms — listed before shorter component forms so the
        # longest-match regex picks the compound first
        "ាំង": "aŋ",
        "ាំ": "am",
        "ុំ": "um",
        "ោះ": "ɔh",
        # Standard vowel diacritics
        "ា": "aː",
        "ិ": "i",
        "ី": "iː",
        "ឹ": "ɨ",
        "ឺ": "ɨː",
        "ុ": "u",
        "ូ": "uː",
        "ួ": "uə",
        "ើ": "əː",
        "ឿ": "ɨə",
        "ៀ": "iə",
        "េ": "eː",
        "ែ": "ɛː",
        "ៃ": "aj",
        "ោ": "oː",
        "ៅ": "aw",
        "ំ": "ɔm",
        "ះ": "ah",
        "ៈ": "aʔ",
    },
    "onset_modifiers": {
        "្": "_",    # subscript marker — forms onset clusters
        "៉": "W",    # musekatond — converts class ² → class ¹
        "៊": "T",    # treisapt   — converts class ¹ → class ²
        "៌": "R",    # robat
        "័": "Q",
        "៏": "G",
        "៑": "V",
    },
    "coda_modifiers": {
        "់": "S",    # bantak — shortens the vowel
        "៎": "+",    # kakabat
        "៍": "X",    # tondokhead
    },
    "punctuation": {
        "(": "(",
        ")": ")",
        "៛": "@",
        "ៜ": ";",
        "៝": "^",
        "។": ".",
        "៕": "|",
        "៖": ":",
        "ៗ": "=",
        "៘": "&",
        "៙": "{",
        "៚": "}",
    },
    "numerals": {
        "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
        "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
        "៰": "0", "៱": "1", "៲": "2", "៳": "3", "៴": "4",
        "៵": "5", "៶": "6", "៷": "7", "៸": "8", "៹": "9",
    },
}


# ── Vowel allophony by consonant class ────────────────────────────────────────
# Format: {ipa_vowel: {"¹": class_1_form, "²": class_2_form}}
# Vowels absent from this table are left unchanged by apply_vowel_allophony().

_ALLOPHONY = {
    "iə": {"¹": "iə",  "²": "iə"},
    "iː": {"¹": "iː",  "²": "iː"},
    "i":  {"¹": "ɛ",   "²": "i"},
    "eː": {"¹": "eː",  "²": "eː"},
    "e":  {"¹": "e",   "²": "e"},
    "ɛː": {"¹": "ɛː",  "²": "ɛː"},
    "ɛ":  {"¹": "ɛ",   "²": "ɛ"},
    "ɨə": {"¹": "ɨə",  "²": "ɨə"},
    "ɨː": {"¹": "ɨː",  "²": "ɨː"},
    "ɨ":  {"¹": "ə",   "²": "ɨ"},
    "əː": {"¹": "əː",  "²": "əː"},
    "ə":  {"¹": "ə",   "²": "ə"},
    "aː": {"¹": "aː",  "²": "aː"},
    "a":  {"¹": "a",   "²": "a"},
    "uə": {"¹": "uə",  "²": "uə"},
    "uː": {"¹": "oː",  "²": "uː"},
    "u":  {"¹": "o",   "²": "u"},
    "oː": {"¹": "oː",  "²": "oː"},
    "o":  {"¹": "o",   "²": "o"},
    "ɔː": {"¹": "ɔː",  "²": "ɔː"},
    "ɔ":  {"¹": "uə",  "²": "ɔ"},
    "ɒː": {"¹": "ɔː",  "²": "ɔː"},
    "ɒ":  {"¹": "uə",  "²": "ɔ"},
}


# ── Coda realizations ─────────────────────────────────────────────────────────
# Applied to the F slot after S/T/W modifier processing, before numeral stripping.
# These are language-level neutralisations, not Lao orthographic conventions.

_CODA_REALIZATIONS = {
    "k²": "ʔ",   # class-2 final /k/ → glottal stop in Brao
}


# ── Closed vowels ──────────────────────────────────────────────────────────────
# Vowels that already encode a final consonant or glide.  The parser treats any
# consonant following one of these vowels as the onset of the NEXT syllable
# rather than a coda of the current one.

_CLOSED_VOWELS = {
    "ɔm",   # ំ  — inherent final /m/
    "am",   # ាំ — inherent final /m/
    "um",   # ុំ — inherent final /m/
    "aŋ",   # ាំង — inherent final /ŋ/
    "ah",   # ះ  — inherent final /h/
    "ɔh",   # ោះ — inherent final /h/
    "aʔ",   # ២  — inherent final /ʔ/
    "aj",   # ២  — inherent final glide /j/
    "aw",   # ២  — inherent final glide /w/
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_flat_dict(conv_dict: dict) -> dict:
    flat = {}
    for sub in conv_dict.values():
        flat.update(sub)
    return flat


def _khmer_to_ipa(text: str, flat_dict: dict) -> str:
    """Regex-substitute Khmer → IPA using longest-match on flat_dict."""
    pattern = re.compile(
        "|".join(re.escape(k) for k in sorted(flat_dict, key=len, reverse=True))
    )
    return pattern.sub(lambda m: flat_dict[m.group(0)], text)


# ── Pipeline interface ────────────────────────────────────────────────────────

def build_pipeline() -> tuple:
    """
    Build the segment lists and flat conversion dict from the hardcoded data.

    Returns:
        (flat_dict, segments_dict)
        segments_dict also carries allophony, coda_realizations, and conv_dict.
    """
    flat_dict = _build_flat_dict(_CONV_DICT)
    segments_dict = define_segments(_CONV_DICT)
    segments_dict["allophony"] = _ALLOPHONY
    segments_dict["coda_realizations"] = _CODA_REALIZATIONS
    segments_dict["closed_vowels"] = _CLOSED_VOWELS
    segments_dict["conv_dict"] = _CONV_DICT
    return flat_dict, segments_dict


def apply_ipa_fixups(syllables: list) -> list:
    """
    Apply Brao-specific IPA fixups to syllable dicts after allophony.

    Rules are applied in order:
    1. F == "b"           → F = "p"  (final-stop devoicing)
    2. V contains m/ŋ/j   → strip consonant from V; set F to that consonant
    3. V == "ah"          → F = "h", V = "a"
    4. V contains "h"     → strip "h" from V; F = "h"
    5. "ia"/"ɨa"/"ua" in V → normalise to "iə"/"ɨə"/"uə"
    6. len(V) == 1 and F == "∅" → F = "ʔ"  (short open syllable → glottal coda)
    """
    _NULL = "∅"
    result = []
    for syl in syllables:
        if syl.get("error"):
            result.append(syl)
            continue
        syl = dict(syl)

        # Rule 1: final /b/ → /p/
        if syl.get("F") == "b":
            syl["F"] = "p"

        # Rule 2: vowel with embedded nasal/glide → split into V and F
        v = syl.get("V", "")
        for ch in ("m", "ŋ", "j"):
            if ch in v:
                syl["V"] = v.replace(ch, "")
                syl["F"] = ch
                break

        # Rule 3: "ah" substring in V → remove "ah", set F = "h"; if V empty → "a"
        if "ah" in syl.get("V", ""):
            v = syl["V"].replace("ah", "")
            syl["F"] = "h"
            syl["V"] = v if v else "a"
        # Rule 4: any remaining "h" in V → strip and move to F
        elif "h" in syl.get("V", ""):
            syl["F"] = "h"
            syl["V"] = syl["V"].replace("h", "")

        # Rule 5: diphthong notation normalisation
        v = syl.get("V", "")
        if v == "ia":
            syl["V"] = "iə"
        elif v == "ɨa":
            syl["V"] = "ɨə"
        elif v == "ua":
            syl["V"] = "uə"

        # Rule 6: short vowel in open syllable → glottal-stop coda
        v = syl.get("V", "")
        f = syl.get("F", _NULL)
        if len(v) == 1 and f == _NULL:
            syl["F"] = "ʔ"

        result.append(syl)
    return result


def run_pipeline(text: str, flat_dict: dict, segments_dict: dict) -> tuple:
    """
    Convert a Khmer-script Brao string to IPA and parse into syllable dicts.

    Args:
        text:          Khmer-script input.
        flat_dict:     From build_pipeline().
        segments_dict: From build_pipeline().

    Returns:
        (ipa_string, syllable_dicts)
        syllable_dicts is a list of P/R/C/M/V/F/T dicts with allophony applied.
    """
    if not isinstance(text, str):
        return (None, [])
    text = text.replace("\u200b", "")   # strip zero-width spaces
    text = text.replace("\u002d", " ")  # hyphens → spaces

    try:
        ipa = _khmer_to_ipa(text, flat_dict)
    except Exception:
        return (None, [])

    syllables = parse_syllables(ipa, segments_dict)
    syllables = apply_consonant_modifiers(
        syllables, f_subs=segments_dict.get("coda_realizations")
    )
    syllables = apply_vowel_allophony(syllables, segments_dict.get("allophony", {}))
    syllables = apply_ipa_fixups(syllables)
    return ipa, syllables
