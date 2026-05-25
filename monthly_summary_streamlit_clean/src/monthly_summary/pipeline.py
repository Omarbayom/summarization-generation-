from __future__ import annotations

from typing import Any, Callable, Dict, Tuple

import pandas as pd

from .config import load_config, output_dir_from_config
from .emailer import send_email_with_attachments
from .excel_parser import aggregate_items_for_llm, extract_items_from_xlsx
from .pdf_renderer import export_summary_pdf
from .summarizer import make_summaries
from .text_utils import normalize_text


def _clean_df_text(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    for col in cleaned.columns:
        if cleaned[col].dtype == object:
            cleaned[col] = cleaned[col].map(normalize_text)
    return cleaned


def save_outputs(summary_df: pd.DataFrame, bigger_df: pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, str]:
    """Save only summary and bigger_summary outputs."""
    out = output_dir_from_config(cfg)

    summary_df = _clean_df_text(summary_df)
    bigger_df = _clean_df_text(bigger_df)

    xlsx_path = out / "summary_and_bigger_summary.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="summary", index=False)
        bigger_df.to_excel(writer, sheet_name="bigger_summary", index=False)

    pdf_cfg = cfg.get("pdf", {})
    one_page = bool(pdf_cfg.get("one_team_per_page", False))
    summary_pdf = out / "summary_may26_style.pdf"
    bigger_pdf = out / "bigger_summary_may26_style.pdf"
    export_summary_pdf(
        summary_df,
        text_col="summary",
        output_pdf=summary_pdf,
        report_title=pdf_cfg.get("summary_title", "Executive Summary Report"),
        one_team_per_page=one_page,
    )
    export_summary_pdf(
        bigger_df,
        text_col="bigger_summary",
        output_pdf=bigger_pdf,
        report_title=pdf_cfg.get("bigger_summary_title", "Detailed Summary Report"),
        one_team_per_page=one_page,
    )

    return {
        "xlsx": str(xlsx_path),
        "summary_pdf": str(summary_pdf),
        "bigger_summary_pdf": str(bigger_pdf),
    }


def run_pipeline(
    input_xlsx: str,
    config_path: str | None = "config.yaml",
    overrides: Dict[str, Any] | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, str]]:
    cfg = load_config(config_path, overrides=overrides)

    def progress(fraction: float, message: str) -> None:
        if progress_callback is not None:
            progress_callback(fraction, message)

    progress(0.02, "Starting pipeline")
    raw_df = extract_items_from_xlsx(input_xlsx, cfg)
    if raw_df.empty:
        raise ValueError(
            "No meeting items were extracted. Check config.yaml markers and Excel layout. "
            "The parser expects repeated Category / Team columns and Yesterday/Today sections."
        )
    progress(0.12, f"Extracted {len(raw_df)} meeting items")

    agg_df = aggregate_items_for_llm(raw_df)
    if agg_df.empty:
        raise ValueError("No aggregated team items were created after filtering empty notes.")
    progress(0.18, f"Prepared {len(agg_df)} team/category groups")

    summary_df, bigger_df = make_summaries(agg_df, cfg, progress_callback=progress, start_fraction=0.18, end_fraction=0.84)

    progress(0.88, "Saving Excel and May26-style PDF outputs")
    paths = save_outputs(summary_df, bigger_df, cfg)
    progress(0.94, "Saved Excel and PDF outputs")

    if cfg.get("email", {}).get("enabled"):
        progress(0.96, "Sending email with attachments")
        send_email_with_attachments(cfg, [paths["xlsx"], paths["summary_pdf"], paths["bigger_summary_pdf"]])
        progress(0.99, "Email sent")

    progress(1.0, "Done")
    return summary_df, bigger_df, paths
