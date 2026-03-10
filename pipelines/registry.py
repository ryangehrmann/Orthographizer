"""
pipelines/registry.py
Registry of available transcoding pipelines.
Each entry maps a display label to metadata and the module that implements it.

To add a new pipeline:
  1. Create pipelines/<name>.py with build_pipeline() and run_pipeline()
  2. Add an entry to PIPELINES below
The Streamlit UI auto-discovers pipelines from this dict.
"""

PIPELINES = {
    "Brao (Khmer script) → IPA": {
        "source_lang": "Brao",
        "source_script": "Khmer",
        "target": "IPA",
        "module": "pipelines.brao_khmer_ipa",
    },
    "Brao (Khmer script) → Lao": {
        "source_lang": "Brao",
        "source_script": "Khmer",
        "target": "Lao",
        "module": "pipelines.brao_khmer_lao",
    },
}
