# Orthographizer

A web application for transcoding language data written in national scripts of Mainland Southeast Asia into IPA phonemic notation and/or other national scripts.

**Live app:** https://orthographizer.streamlit.app

---

## Transcoding pipelines

| Pipeline | Source | Target |
|----------|--------|--------|
| Brao (Khmer script) → IPA | Brao language in Khmer script | IPA phonemic notation |
| Brao (Khmer script) → Lao | Brao language in Khmer script | Lao script |

---

## Input modes

### Dictionary / word list (`.xlsx`)
Upload a spreadsheet with a column of Khmer-script headwords (`entry_ortho`). The app transcodes every entry and returns a formatted `.xlsx` database with one row per syllable and columns for each IPA segment slot (P R C M V F T).

### Running text (`.txt` or `.docx`)
Upload a text file. Khmer tokens are detected automatically and replaced with their IPA/Lao equivalents. Two output files are produced:
- **IPA-only** `.docx` — Khmer replaced inline with IPA (Lao in parentheses when available)
- **Interlinear** `.html` — three-line stacked layout: Lao / IPA / Khmer script

---

## Project structure

```
app.py                  Streamlit entry point
core/
  conversion.py         Khmer → IPA character substitution
  parsing.py            IPA syllable segmentation
  modifiers.py          S/T/W modifier processing, tone, allophony
  lao_assembly.py       IPA → Lao script assembly
pipelines/
  registry.py           Pipeline registry (auto-discovered by the UI)
  brao_khmer_ipa.py     Brao Khmer → IPA pipeline
  brao_khmer_lao.py     Brao Khmer → Lao pipeline
processors/
  xlsx_input.py         .xlsx column detection and validation
  xlsx_output.py        Formatted .xlsx output with formulas
  text_input.py         .txt / .docx reader, Khmer token detection
  text_output.py        IPA-only .docx and interlinear .html output
data/
  brao_ipa_lao_conversion_table.xlsx
  khmer_ipa_conversion_table.xlsx
  (other conversion tables)
requirements.txt
Orthographizer_User_Guide.docx
```

---

## Requirements

```
streamlit
pandas
openpyxl
python-docx
charset-normalizer
```

---

## User guide

See `Orthographizer_User_Guide.docx` for full documentation including character maps and transcoding rules.
