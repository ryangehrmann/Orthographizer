"""
core/parsing.py
IPA syllable segmentation and parsing for the iambic-disyllable template.
Segments: P (presyllable onset) / R (presyllable rime) / C (main onset) /
          M (medial) / V (vowel) / F (final/coda) / T (tone, TBD)
"""
import re


def define_segments(conv_dict: dict) -> dict:
    """
    Build lists of valid IPA segments from the conversion dict.
    Returns a dict with keys: onsets, codas, vowels, punctuation, numerals.
    """
    onsets = list(conv_dict["onsets"].values())
    onset_modifiers = list(conv_dict["onset_modifiers"].values())
    for mod in onset_modifiers:
        onsets = onsets + [o + mod for o in conv_dict["onsets"].values()]

    codas = list(conv_dict["codas"].values())
    coda_modifiers = list(conv_dict["coda_modifiers"].values())
    for mod in coda_modifiers:
        codas = codas + [c + mod for c in conv_dict["codas"].values()]

    vowels = list(conv_dict["vowels"].values())
    punctuation = list(conv_dict["punctuation"].values())
    numerals = list(conv_dict["numerals"].values())

    return {
        "vowels": vowels,
        "onsets": onsets,
        "codas": codas,
        "punctuation": punctuation,
        "numerals": numerals,
    }


def split_by_segments(word: str, segments_list: list) -> list:
    """
    Split an IPA string into a list of known segment chunks.
    Longer segments are matched first to avoid spurious partial matches.

    Known bug: variant orthographic form អឹ្យ (vowel interrupts cluster)
    not converted correctly — ignore for now.
    """
    if not isinstance(word, str):
        return ["error"]

    sorted_segs = sorted(segments_list, key=len, reverse=True)
    pattern = re.compile(
        "(" + "|".join(re.escape(v) for v in sorted_segs) + ")"
    )
    parts = pattern.split(word)
    return [p for p in parts if p]


def parse_syllables(text: str, segments_dict: dict) -> list:
    """
    Parse an IPA string into a list of syllable dicts with P/R/C/M/V/F/T slots.

    Each space-separated chunk produces one or more dicts. Segments with dual
    roles are resolved by trying all valid presyllable + main-syllable
    combinations.  When multiple parses are valid, the fewest syllables is
    preferred; within equal syllable counts, the one with the lowest priority
    sum is preferred, and 'ambiguous' is set to True.
    """
    if not isinstance(text, str):
        return []

    onsets = segments_dict["onsets"]
    vowels = segments_dict["vowels"]
    codas = segments_dict["codas"]
    punctuation = segments_dict["punctuation"]
    numerals = segments_dict["numerals"]
    segments_list = onsets + vowels + codas + punctuation + numerals

    onset_set = set(onsets)
    vowel_set = set(vowels)
    coda_set = set(codas)
    punct_set = set(punctuation)
    num_set = set(numerals)
    medial_set = {"r²", "l²"}
    closed_vowel_set = set(segments_dict.get("closed_vowels", []))

    def is_onset(seg):
        return seg in onset_set and not seg.endswith("_")

    def is_onset_(seg):
        return seg in onset_set and seg.endswith("_")

    def is_vowel(seg):
        if seg in vowel_set:
            return True
        if len(seg) > 1 and any(
            seg.startswith(v) and seg[len(v):] in vowel_set
            for v in vowel_set
            if len(v) < len(seg)
        ):
            return True
        return False

    def is_coda(seg):
        return seg in coda_set

    def is_medial(seg):
        return seg in medial_set

    def is_closed_vowel(seg):
        """Return True if this vowel already encodes a final consonant/glide."""
        return seg in closed_vowel_set

    def blank():
        return {
            "P": "", "R": "", "C": "", "M": "", "V": "", "F": "", "T": "",
            "ambiguous": False, "error": "", "segments": [],
        }

    def make_word(P, R, C, M, V, F, segments):
        return {
            "P": P, "R": R, "C": C, "M": M, "V": V, "F": F, "T": "",
            "ambiguous": False, "error": "", "segments": segments,
        }

    def try_main_prefix(s):
        results = []
        n = len(s)

        if n >= 1 and (is_onset(s[0]) or is_onset_(s[0])):
            results.append((s[0].rstrip("_"), "", "ɔː", "∅", 1))

        if n >= 2:
            if is_onset_(s[0]) and is_medial(s[1]):
                results.append((s[0].rstrip("_"), s[1], "ɔː", "∅", 2))
            if is_onset(s[0]) and is_coda(s[1]):
                results.append((s[0], "", "ɔː", s[1], 2))
            if is_onset(s[0]) and is_vowel(s[1]):
                results.append((s[0], "", s[1], "∅", 2))

        if n >= 3:
            if is_onset_(s[0]) and is_medial(s[1]) and is_coda(s[2]):
                results.append((s[0].rstrip("_"), s[1], "ɔː", s[2], 3))
            if is_onset_(s[0]) and is_medial(s[1]) and is_vowel(s[2]):
                results.append((s[0].rstrip("_"), s[1], s[2], "∅", 3))
            if is_onset(s[0]) and is_vowel(s[1]) and is_coda(s[2]) and not is_closed_vowel(s[1]):
                results.append((s[0], "", s[1], s[2], 3))

        if n >= 4:
            if (
                is_onset_(s[0])
                and is_medial(s[1])
                and is_vowel(s[2])
                and is_coda(s[3])
                and not is_closed_vowel(s[2])
            ):
                results.append((s[0].rstrip("_"), s[1], s[2], s[3], 4))

        return results

    def get_presyl_options(chunk):
        n = len(chunk)
        options = [("", "", 0, 0)]  # no presyllable

        if n >= 2 and is_onset(chunk[0]):
            options.append((chunk[0], "a", 1, 5))

        if n >= 3 and is_onset(chunk[0]) and chunk[1] == "ɔm":
            options.append((chunk[0], "m", 2, 2))

        if n >= 3 and is_onset(chunk[0]) and chunk[1] == "ŋ²S":
            options.append((chunk[0], "ŋ", 2, 2))

        if n >= 3 and is_onset(chunk[0]) and chunk[1] == "n²S":
            options.append((chunk[0], "n", 2, 2))

        if n >= 3 and is_onset_(chunk[0]) and chunk[1] in medial_set:
            options.append((chunk[0].rstrip("_"), chunk[1], 2, 3))

        return options

    def solve(chunk, memo=None):
        if memo is None:
            memo = {}
        key = tuple(chunk)
        if key in memo:
            return memo[key]
        if not chunk:
            memo[key] = [(0, [])]
            return [(0, [])]

        all_parses = []
        for P, R, presyl_consumed, presyl_priority in get_presyl_options(chunk):
            after_presyl = chunk[presyl_consumed:]
            for C, M, V, F, main_consumed in try_main_prefix(after_presyl):
                total_consumed = presyl_consumed + main_consumed
                syl_segs = chunk[:total_consumed]
                syl = make_word(P, R, C, M, V, F, syl_segs)
                remainder = chunk[total_consumed:]
                if not remainder:
                    all_parses.append((presyl_priority, [syl]))
                else:
                    for rest_pri, rest_syls in solve(remainder, memo):
                        all_parses.append(
                            (presyl_priority + rest_pri, [syl] + rest_syls)
                        )

        memo[key] = all_parses
        return all_parses

    chunks = text.split(" ")
    chunks = [split_by_segments(chunk, segments_list) for chunk in chunks]

    results = []

    for chunk in chunks:
        if not chunk:
            continue

        if all(seg in punct_set or seg in num_set for seg in chunk):
            word = blank()
            word["segments"] = chunk
            word["error"] = "".join(chunk)
            results.append(word)
            continue

        trailing = ""
        while chunk and (chunk[-1] in punct_set or chunk[-1] in num_set):
            trailing = chunk[-1] + trailing
            chunk = chunk[:-1]

        if not chunk:
            word = blank()
            word["error"] = trailing
            results.append(word)
            continue

        # Merge consecutive vowels into compound vowels
        merged = [chunk[0]]
        for seg in chunk[1:]:
            if is_vowel(merged[-1]) and is_vowel(seg):
                merged[-1] = merged[-1] + seg
            else:
                merged.append(seg)
        chunk = merged

        all_parses = solve(chunk)

        if not all_parses:
            word = blank()
            word["segments"] = chunk
            word["error"] = "".join(chunk) + trailing
            results.append(word)
        else:
            all_parses.sort(key=lambda x: (len(x[1]), x[0]))
            best_pri, best_syls = all_parses[0]
            best_n = len(best_syls)

            same_len_parses = [p for p in all_parses if len(p[1]) == best_n]
            ambiguous = len(same_len_parses) > 1
            if ambiguous:
                for syl in best_syls:
                    syl["ambiguous"] = True

            if trailing:
                best_syls[-1]["trailing"] = trailing
            results.extend(best_syls)

    return results
