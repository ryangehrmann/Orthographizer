"""
app.py
Orthographizer — Streamlit web app for script transcoding.

Run with:
    streamlit run app.py
"""
import importlib
import streamlit as st

from pipelines.registry import PIPELINES
from processors.xlsx_input import (
    load_xlsx,
    detect_entry_column,
    detect_index_column,
    validate_entry_column,
    prepare_df,
)
from processors.xlsx_output import build_output_rows, write_xlsx
from processors.text_input import read_text_file
from processors.text_output import build_ipa_only_docx, build_interlinear_html


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Orthographizer",
    page_icon="🔤",
    layout="centered",
)

st.title("Orthographizer")
st.caption("Script transcoding tool")

# ── Pipeline selection ───────────────────────────────────────────────────────
st.header("1 · Transcoding pipeline")
pipeline_label = st.selectbox(
    "Select transcoding pipeline",
    options=list(PIPELINES.keys()),
    help="Choose the source language/script and transcoding target.",
)

pipeline_meta = PIPELINES[pipeline_label]

@st.cache_resource(show_spinner="Loading pipeline…")
def _get_pipeline(module_path: str):
    mod = importlib.import_module(module_path)
    return mod.build_pipeline(), mod.run_pipeline

(flat_dict, segments_dict), run_pipeline = _get_pipeline(pipeline_meta["module"])

st.info(
    f"**Source:** {pipeline_meta['source_lang']} ({pipeline_meta['source_script']} script)  "
    f"→  **Target:** {pipeline_meta['target']}"
)

# ── File type selection ──────────────────────────────────────────────────────
st.header("2 · Upload file")
file_type = st.radio(
    "What kind of file are you uploading?",
    options=["Dictionary / word list (.xlsx)", "Text file (.txt or .docx)"],
    horizontal=True,
)

# ============================================================================
# PATH A: xlsx dictionary / word list
# ============================================================================
if file_type == "Dictionary / word list (.xlsx)":

    uploaded = st.file_uploader(
        "Upload your .xlsx file",
        type=["xlsx"],
        key="xlsx_uploader",
    )

    if uploaded is not None:

        # Size check
        uploaded.seek(0, 2)
        size_mb = uploaded.tell() / (1024 * 1024)
        uploaded.seek(0)
        if size_mb > 50:
            st.warning(
                f"File is {size_mb:.1f} MB — large files may take a while to process."
            )

        # Load
        with st.spinner("Reading file…"):
            df, err = load_xlsx(uploaded)

        if err:
            st.error(err)
            st.stop()

        st.success(f"File loaded — {len(df):,} rows, {len(df.columns)} columns.")

        # ── Entry column detection ───────────────────────────────────────
        entry_col = detect_entry_column(df)

        if entry_col is None:
            st.warning(
                "Could not find a column named **entry_ortho**. "
                "Please select the column that contains the Khmer-script entries."
            )
            entry_col = st.selectbox(
                "Khmer-script entry column",
                options=list(df.columns),
                key="entry_col_select",
            )

        # Warn if column doesn't look like Khmer
        warn = validate_entry_column(df, entry_col)
        if warn:
            st.warning(warn)

        # ── Index column detection ───────────────────────────────────────
        idx_info = detect_index_column(df)
        index_col = None
        generate_index = False

        if idx_info["found"]:
            index_col = idx_info["found"]
            st.info(f"Using **{index_col}** as the index column.")
        elif idx_info["needs_user_input"] and idx_info["candidate"]:
            candidate = idx_info["candidate"]
            use_candidate = st.radio(
                f"The column **{candidate!r}** looks like it might be an index "
                f"(mostly integers). Use it as the index?",
                options=["Yes, use it as the index", "No, generate a new index"],
                key="index_radio",
            )
            if use_candidate.startswith("Yes"):
                index_col = candidate
            else:
                generate_index = True
        else:
            st.info("No index column found — a sequential index will be created.")
            generate_index = True

        # ── Process button ───────────────────────────────────────────────
        if st.button("Process", type="primary", key="process_xlsx"):

            with st.spinner("Preparing data…"):
                df_ready = prepare_df(
                    df,
                    entry_col=entry_col,
                    index_col=index_col,
                    generate_index=generate_index,
                )

            progress_bar = st.progress(0, text="Transcoding entries…")
            total = len(df_ready)

            # Build output row by row for progress tracking
            from processors.xlsx_output import FIXED_COLS
            import pandas as pd
            from core.conversion import find_unknown_chars

            rows = []
            extra_cols = [c for c in df_ready.columns if c not in ("entry_ortho", "index")]
            errors = []

            for i, (_, row) in enumerate(df_ready.iterrows()):
                idx = row.get("index", i)
                entry_ortho = row.get("entry_ortho", "")
                extra = {col: row.get(col, "") for col in extra_cols}

                try:
                    ipa, syllables = run_pipeline(entry_ortho, flat_dict, segments_dict)
                except Exception as e:
                    errors.append(str(e))
                    syllables = []
                    ipa = None

                if not syllables:
                    rows.append({
                        "index": idx, "sub_index": 0,
                        "entry_ortho": entry_ortho, "entry": ipa or "",
                        "word_lao": "", "word": "",
                        "P": "", "R": "", "C": "", "M": "", "V": "", "F": "", "T": "",
                        "ambiguous": False,
                        **extra,
                    })
                else:
                    for sub_idx, syl in enumerate(syllables):
                        rows.append({
                            "index": idx, "sub_index": sub_idx,
                            "entry_ortho": entry_ortho, "entry": ipa or "",
                            "word_lao": syl.get("word_lao", ""),
                            "word": "",
                            "P": syl.get("P", ""), "R": syl.get("R", ""),
                            "C": syl.get("C", ""), "M": syl.get("M", ""),
                            "V": syl.get("V", ""), "F": syl.get("F", ""),
                            "T": syl.get("T", ""),
                            "ambiguous": syl.get("ambiguous", False),
                            **extra,
                        })

                if (i + 1) % max(1, total // 100) == 0 or i == total - 1:
                    progress_bar.progress(
                        (i + 1) / total,
                        text=f"Transcoding… {i + 1:,}/{total:,}"
                    )

            progress_bar.empty()

            output_df = pd.DataFrame(rows)
            final_extra = [c for c in output_df.columns if c not in FIXED_COLS]
            output_df = output_df[FIXED_COLS + final_extra]

            n_ambiguous = int(output_df["ambiguous"].sum())
            ambig_rate = n_ambiguous / max(len(output_df), 1)

            # Check for unknown chars in entry column
            unknown_df = find_unknown_chars(
                df_ready["entry_ortho"],
                segments_dict.get("conv_dict", flat_dict),
            )

            # ── Stats ────────────────────────────────────────────────────
            col1, col2, col3 = st.columns(3)
            col1.metric("Entries processed", f"{total:,}")
            col2.metric("Output rows", f"{len(output_df):,}")
            col3.metric("Ambiguous", f"{n_ambiguous:,}")

            if errors:
                st.warning(f"{len(errors)} entries raised errors during processing.")
                with st.expander("Show errors"):
                    st.write(errors[:50])

            if not unknown_df.empty:
                st.warning(
                    f"{len(unknown_df)} character(s) not found in the conversion table:"
                )
                st.dataframe(unknown_df, use_container_width=False)

            if ambig_rate > 0.30:
                st.warning(
                    f"{ambig_rate:.0%} of output rows are flagged as ambiguous. "
                    "You may want to review the conversion table."
                )

            # ── Write xlsx ───────────────────────────────────────────────
            with st.spinner("Formatting output file…"):
                xlsx_bytes = write_xlsx(output_df)

            base_name = uploaded.name.rsplit(".", 1)[0]
            st.download_button(
                label="⬇️  Download output (.xlsx)",
                data=xlsx_bytes,
                file_name=f"{base_name}_orthographizer.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

# ============================================================================
# PATH B: text file
# ============================================================================
else:
    uploaded = st.file_uploader(
        "Upload your text file",
        type=["txt", "docx"],
        key="text_uploader",
    )

    if uploaded is not None:

        # Clear cached results when a new file is uploaded
        if st.session_state.get("text_source_name") != uploaded.name:
            st.session_state.pop("text_results", None)
            st.session_state["text_source_name"] = uploaded.name

        # Size check
        uploaded.seek(0, 2)
        size_mb = uploaded.tell() / (1024 * 1024)
        uploaded.seek(0)
        if size_mb > 20:
            st.warning(
                f"File is {size_mb:.1f} MB — this may take a moment to process."
            )

        with st.spinner("Reading file…"):
            paragraphs, err = read_text_file(uploaded, uploaded.name)

        if err:
            st.error(err)
            st.stop()

        n_paragraphs = sum(1 for p in paragraphs if p)
        n_khmer_tokens = sum(
            1 for p in paragraphs for t, k in p if k and t.strip()
        )

        if n_khmer_tokens == 0:
            st.warning(
                "No Khmer text was detected in the uploaded file. "
                "Make sure the file contains characters in the Khmer Unicode block (U+1780–U+17FF)."
            )
            st.stop()

        st.success(
            f"File loaded — {n_paragraphs:,} paragraph(s), "
            f"{n_khmer_tokens:,} Khmer token(s) found."
        )

        if st.button("Process", type="primary", key="process_text"):
            with st.spinner("Transcoding…"):
                ipa_bytes = build_ipa_only_docx(
                    paragraphs, run_pipeline, flat_dict, segments_dict
                )
                interlinear_bytes = build_interlinear_html(
                    paragraphs, run_pipeline, flat_dict, segments_dict
                )
            base_name = uploaded.name.rsplit(".", 1)[0]
            st.session_state["text_results"] = {
                "ipa_bytes": ipa_bytes,
                "interlinear_bytes": interlinear_bytes,
                "base_name": base_name,
            }

        if "text_results" in st.session_state:
            import io, zipfile
            r = st.session_state["text_results"]
            ipa_bytes = r["ipa_bytes"]
            interlinear_bytes = r["interlinear_bytes"]
            base_name = r["base_name"]

            # Build zip of both files
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                zf.writestr(f"{base_name}_ipa.docx", ipa_bytes)
                zf.writestr(f"{base_name}_interlinear.html", interlinear_bytes)
            zip_bytes = zip_buf.getvalue()

            st.success("Done! Download your output files below.")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.download_button(
                    label="⬇️  IPA-only (.docx)",
                    data=ipa_bytes,
                    file_name=f"{base_name}_ipa.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="dl_ipa",
                )
            with col2:
                st.download_button(
                    label="⬇️  Interlinear (.html)",
                    data=interlinear_bytes,
                    file_name=f"{base_name}_interlinear.html",
                    mime="text/html",
                    key="dl_interlinear",
                )
            with col3:
                st.download_button(
                    label="⬇️  Both (.zip)",
                    data=zip_bytes,
                    file_name=f"{base_name}_orthographizer.zip",
                    mime="application/zip",
                    key="dl_both",
                )
            st.caption(
                "Ambiguous sequences are highlighted in red and wrapped in { }."
            )

# ── Reset ─────────────────────────────────────────────────────────────────────
st.divider()
if st.button("↺  Reset", key="reset"):
    st.session_state.clear()
    st.rerun()
