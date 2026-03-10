"""
processors/xlsx_input.py
Handles reading and validating an uploaded .xlsx dictionary/word-list file.

Returns a normalised DataFrame and the resolved column names for the entry
and index columns.  All interactive prompts are expressed as return values
so the caller (Streamlit app) can render them as widgets.
"""
import io
import pandas as pd


# ── Khmer Unicode block: U+1780–U+17FF ─────────────────────────────────────
def _looks_like_khmer(series: pd.Series, threshold: float = 0.3) -> bool:
    """True if ≥ threshold fraction of non-empty cells contain a Khmer char."""
    khmer_range = range(0x1780, 0x1800)
    count = 0
    total = 0
    for val in series.dropna().astype(str):
        total += 1
        if any(ord(c) in khmer_range for c in val):
            count += 1
    if total == 0:
        return False
    return (count / total) >= threshold


def _mostly_integer(series: pd.Series, threshold: float = 0.8) -> bool:
    """True if ≥ threshold fraction of non-empty cells look like integers."""
    total = series.dropna().shape[0]
    if total == 0:
        return False
    try:
        numeric = pd.to_numeric(series.dropna(), errors="coerce")
        int_like = numeric.dropna().apply(lambda x: x == int(x)).sum()
        return (int_like / total) >= threshold
    except Exception:
        return False


# ── Public API ───────────────────────────────────────────────────────────────

def load_xlsx(file_obj) -> tuple[pd.DataFrame | None, str | None]:
    """
    Read an xlsx file object into a DataFrame.

    Returns:
        (df, error_message) — error_message is None on success.
    """
    try:
        df = pd.read_excel(file_obj, sheet_name="Sheet1", engine="openpyxl")
    except Exception:
        try:
            # Retry without sheet_name restriction (some files use different names)
            file_obj.seek(0)
            df = pd.read_excel(file_obj, engine="openpyxl")
        except Exception as e:
            return None, f"Could not read file: {e}"

    if df.empty:
        return None, "The uploaded file appears to be empty."

    return df, None


def detect_entry_column(df: pd.DataFrame) -> str | None:
    """
    Return the name of the entry_ortho column if it exists, else None.
    """
    if "entry_ortho" in df.columns:
        return "entry_ortho"
    return None


def detect_index_column(df: pd.DataFrame) -> dict:
    """
    Inspect the DataFrame and return a dict describing the index situation:

    {
        "found": str | None,      # name of a definitive index column, or None
        "candidate": str | None,  # name of a column that *looks* like an index
        "needs_user_input": bool,
    }
    """
    if "index" in df.columns:
        return {"found": "index", "candidate": None, "needs_user_input": False}

    # Look for a non-'index' column that is mostly integers
    candidates = [
        col for col in df.columns
        if col != "index" and _mostly_integer(df[col])
    ]
    if candidates:
        return {
            "found": None,
            "candidate": candidates[0],
            "needs_user_input": True,
        }

    return {"found": None, "candidate": None, "needs_user_input": False}


def validate_entry_column(df: pd.DataFrame, col: str) -> str | None:
    """
    Verify that the chosen column contains Khmer-looking text.
    Returns a warning string if suspicious, None if OK.
    """
    if col not in df.columns:
        return f"Column '{col}' not found in the file."
    if not _looks_like_khmer(df[col]):
        return (
            f"Column '{col}' does not appear to contain Khmer script "
            "(fewer than 30% of cells contain Khmer characters). "
            "Proceed with caution."
        )
    return None


def prepare_df(
    df: pd.DataFrame,
    entry_col: str,
    index_col: str | None,
    generate_index: bool = False,
) -> pd.DataFrame:
    """
    Normalise the DataFrame: strip zero-width spaces, convert hyphens, assign index.

    Args:
        df:             Raw DataFrame from load_xlsx.
        entry_col:      Name of the Khmer-script entry column.
        index_col:      Name of the index column, or None.
        generate_index: If True and index_col is None, create a sequential index.

    Returns:
        Normalised DataFrame with guaranteed 'entry_ortho' and 'index' columns.
    """
    df = df.copy()

    # Rename entry column to standard name if needed
    if entry_col != "entry_ortho":
        df = df.rename(columns={entry_col: "entry_ortho"})

    # Normalise text
    df["entry_ortho"] = (
        df["entry_ortho"]
        .astype(str)
        .str.replace("\u200b", "", regex=False)   # zero-width space
        .str.replace("\u002d", " ", regex=False)  # hyphen → space
        .str.strip()
    )

    # Resolve index
    if index_col and index_col in df.columns:
        if index_col != "index":
            df = df.rename(columns={index_col: "index"})
    elif generate_index:
        df.insert(0, "index", range(len(df)))
    # else: no index; caller will handle it

    return df
