"""
pipelines/brao_khmer_lao.py
Pipeline: Brao (Khmer script) → Lao script

Chains the Brao Khmer→IPA pipeline, then assembles Lao script from the
processed IPA syllable dicts using the Brao-specific maps defined here.

All data is hardcoded; no external files are required.
"""
from pipelines.brao_khmer_ipa import (
    build_pipeline as _build_ipa,
    run_pipeline as _run_ipa,
)
from core.lao_assembly import apply_lao_conversion


# ── IPA → Lao glyph map ───────────────────────────────────────────────────────
# Flat map used for the final glyph-substitution pass on the assembled IPA string.
# Longest-match regex is applied, so multi-char keys (kʰ, aː, ʔˈ …) take
# priority over their component characters.
#
# Consonants: bare IPA (no class numeral) → Lao letter
# Vowel components: IPA token as it appears in a rime template → Lao diacritic
#                   or leading letter

_GLYPH_MAP = {
    # ── Consonants ─────────────────────────────────────────────────────────────
    "g":   "ກຼ",
    "k":   "ກ",
    "kʰ":  "ຄ",
    "ŋ":   "ງ",
    "ʄ":   "ຢຼ",
    "ɟ":   "ຈຼ",
    "c":   "ຈ",
    "cʰ":  "ຊ",
    "s":   "ສ",
    "ɲ":   "ຍ",
    "ɗ":   "ດຼ",
    "d":   "ດ",
    "t":   "ຕ",
    "tʰ":  "ທ",
    "n":   "ນ",
    "ɓ":   "ບຼ",
    "b":   "ບ",
    "p":   "ປ",
    "pʰ":  "ພ",
    "f":   "ຟ",
    "m":   "ມ",
    "j":   "ຢ",
    "r":   "ຣ",
    "l":   "ລ",
    "w":   "ວ",
    "h":   "ຮ",
    "ʔ":   "ອ",
    "ɔ":   "ອ",   # used in closed-ɔ rime template to avoid "aʔ"→"ະ" collision
    "∅":   "",
    # ── Vowel components (used inside rime templates) ──────────────────────────
    # Listed longest-first within the map; the regex engine sorts by length.
    "iː":  "ີ",
    "i":   "ິ",
    "ɨː":  "ື",
    "ɨ":   "ຶ",
    "uː":  "ູ",
    "u":   "ຸ",
    "eː":  "ເ",
    "oː":  "ໂ",
    "o":   "ົ",
    "ɛː":  "ແ",
    "aː":  "າ",
    "a":   "ັ",
    "aʔ":  "ະ",
    "ɔː":  "ໍ",
    "ia":  "ຽ",
    "aj":  "ໄ",
    "am":  "ຳ",
    # ── Diacritics ─────────────────────────────────────────────────────────────
    "ˈ":   "໌",    # karan / silent mark (used in glottal-stop and -s coda forms)
}


# ── Coda normalisation map ────────────────────────────────────────────────────
# Maps IPA coda (after Brao S/T/W processing) to the Lao-compatible IPA form
# that will survive the final glyph pass correctly.
#
# Lao orthographic conventions:
#   - Final obstruents are written with their voiced equivalents (p→b, t→d)
#   - Final /j/ is spelled with ɲ (palatal nasal letter)
#   - Final /ɲ/ needs an explicit n + karan to signal palatal nasal
#   - Final /s/ is spelled ɲ + h + karan (archaic digraph)
#   - Glottal stop (ʔ) is handled upstream in _vowel_coda_logic, not here

_CODA_MAP = {
    "p":  "b",
    "t":  "d",
    "c":  "c",
    "k":  "k",
    "m":  "m",
    "n":  "n",
    "ɲ":  "ɲnˈ",    # palatal nasal coda: ຍ + ນ + karan
    "ŋ":  "ŋ",
    "r":  "r",
    "l":  "l",
    "j":  "ɲ",      # palatal glide coda → ɲ (ຍ) in Lao
    "w":  "w",
    "s":  "ɲhˈ",    # fricative coda:  ຍ + ຮ + karan
    "h":  "h",
    # ʔ is intentionally absent — handled by _vowel_coda_logic before this map
}


# ── Vowel rime maps ───────────────────────────────────────────────────────────
# Each value is a list of IPA tokens forming the rime schematic.
# '_' marks the onset consonant position.
# Lists are joined to a string; '_' is then replaced with C+M before the
# final glyph pass converts everything to Lao.

_OPEN_RIME_MAP = {
    # Open syllables (F = ∅)
    "iə":   ["eː", "_", "j"],
    "iəʔ":  ["eː", "_", "j", "aʔ"],
    "iː":   ["_", "iː"],
    "iʔ":   ["_", "i"],
    "eː":   ["eː", "_"],
    "eʔ":   ["eː", "_", "aʔ"],
    "ɛː":   ["ɛː", "_"],
    "ɛʔ":   ["ɛː", "_", "aʔ"],
    "ɨə":   ["eː", "_", "ɨː", "ʔ"],
    "ɨəʔ":  ["eː", "_", "ɨː", "ʔ", "aʔ"],
    "ɨː":   ["_", "ɨː"],
    "ɨʔ":   ["_", "ɨ"],
    "əː":   ["eː", "_", "iː"],
    "əʔ":   ["eː", "_", "i"],
    "aː":   ["_", "aː"],
    "aʔ":   ["_", "aʔ"],
    "am":   ["_", "am"],
    "aj":   ["aj", "_"],
    "aw":   ["eː", "_", "o", "aː"],
    "uə":   ["_", "o", "w"],
    "uəʔ":  ["_", "o", "w", "aʔ"],
    "uː":   ["_", "uː"],
    "uʔ":   ["_", "u"],
    "oː":   ["oː", "_"],
    "oʔ":   ["oː", "_", "aʔ"],
    "ɔː":   ["_", "ɔː"],
    "ɔʔ":   ["eː", "_", "aː", "aʔ"],
}

_CLOSED_RIME_MAP = {
    # Closed syllables (F ≠ ∅)
    "iə":   ["_", "ia"],
    "iː":   ["_", "iː"],
    "i":    ["_", "i"],
    "eː":   ["eː", "_"],
    "e":    ["eː", "_", "a"],
    "ɛː":   ["ɛː", "_"],
    "ɛ":    ["ɛː", "_", "a"],
    "ɨə":   ["eː", "_", "ɨː", "ʔ"],
    "ɨː":   ["_", "ɨː"],
    "ɨ":    ["_", "ɨ"],
    "əː":   ["eː", "_", "iː"],
    "ə":    ["eː", "_", "i"],
    "aː":   ["_", "aː"],
    "a":    ["_", "a"],
    "uə":   ["_", "w"],
    "uː":   ["_", "uː"],
    "u":    ["_", "u"],
    "oː":   ["oː", "_"],
    "o":    ["_", "o"],
    "ɔː":   ["_", "ʔ"],       # open-o vowel letter (ʔ→ອ) flanked by onset+coda
    "ɔ":    ["_", "a", "ɔ"],  # short open-o: sara-a (ັ) + o vowel letter (ອ)
}


# ── Pipeline interface ────────────────────────────────────────────────────────

def build_pipeline() -> tuple:
    """
    Build the Brao Khmer→Lao pipeline.

    Loads the Brao Khmer→IPA pipeline and adds the Lao maps to segments_dict.
    """
    flat_dict, segments_dict = _build_ipa()
    segments_dict["lao_maps"] = (
        _GLYPH_MAP, _CODA_MAP, _OPEN_RIME_MAP, _CLOSED_RIME_MAP
    )
    return flat_dict, segments_dict


def run_pipeline(text: str, flat_dict: dict, segments_dict: dict) -> tuple:
    """
    Convert a Khmer-script Brao string to Lao script.

    Runs the full Brao Khmer→IPA pipeline first, then assembles Lao from the
    resulting syllable dicts.

    Args:
        text:          Khmer-script input.
        flat_dict:     From build_pipeline().
        segments_dict: From build_pipeline(); must carry 'lao_maps'.

    Returns:
        (ipa_string, syllable_dicts)
        ipa_string is the intermediate IPA (used for the 'entry' column).
        Each syllable dict gains a 'word_lao' key with the assembled Lao string.
    """
    ipa, syllables = _run_ipa(text, flat_dict, segments_dict)
    if not syllables:
        return ipa, syllables

    glyph_map, coda_map, open_rime_map, closed_rime_map = segments_dict["lao_maps"]
    syllables = apply_lao_conversion(
        syllables, glyph_map, coda_map, open_rime_map, closed_rime_map
    )
    return ipa, syllables
