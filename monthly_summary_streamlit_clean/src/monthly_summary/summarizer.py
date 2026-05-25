from __future__ import annotations

import time
from typing import Any, Callable, Dict, Tuple

import pandas as pd

from .excel_parser import build_team_input
from .llm import LLMClient
from .prompts import (
    BIGGER_SUMMARY_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    build_bigger_summary_prompt,
    build_summary_prompt,
)
from .text_utils import REQUIRED_SECTIONS, sections_to_text


def make_summaries(
    agg_df: pd.DataFrame,
    cfg: Dict[str, Any],
    progress_callback: Callable[[float, str], None] | None = None,
    start_fraction: float = 0.0,
    end_fraction: float = 1.0,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return only two tables: summary and bigger_summary."""
    if agg_df.empty:
        raise ValueError("No aggregated items found. Check the Excel layout and config markers.")

    client = LLMClient(cfg)
    excel_cfg = cfg.get("excel", {})
    llm_cfg = cfg.get("llm", {})
    max_chars = int(excel_cfg.get("max_input_chars_per_team", 70000))
    sleep_seconds = float(llm_cfg.get("request_sleep_seconds", 0.5))

    teams = sorted(agg_df["Team"].dropna().unique().tolist())
    summary_rows = []
    bigger_rows = []
    total_llm_calls = max(1, len(teams) * 2)
    completed_llm_calls = 0

    def progress(message: str) -> None:
        if progress_callback is None:
            return
        fraction = start_fraction + ((end_fraction - start_fraction) * (completed_llm_calls / total_llm_calls))
        progress_callback(fraction, message)

    for index, team in enumerate(teams, start=1):
        team_input = build_team_input(agg_df, team, max_chars)

        progress(f"Generating summary for {team} ({index}/{len(teams)})")
        summary_sections = client.generate_sections(
            SUMMARY_SYSTEM_PROMPT,
            build_summary_prompt(team, team_input),
            output_kind="summary",
            max_tokens=int(llm_cfg.get("summary_max_tokens", 2500)),
            required_sections=REQUIRED_SECTIONS,
        )
        summary_rows.append({"Team": team, "summary": sections_to_text(summary_sections, REQUIRED_SECTIONS)})
        completed_llm_calls += 1
        progress(f"Finished summary for {team}")
        time.sleep(sleep_seconds)

        progress(f"Generating bigger_summary for {team} ({index}/{len(teams)})")
        bigger_sections = client.generate_sections(
            BIGGER_SUMMARY_SYSTEM_PROMPT,
            build_bigger_summary_prompt(team, team_input),
            output_kind="bigger_summary",
            max_tokens=int(llm_cfg.get("bigger_summary_max_tokens", 5500)),
            required_sections=REQUIRED_SECTIONS,
        )
        bigger_rows.append({"Team": team, "bigger_summary": sections_to_text(bigger_sections, REQUIRED_SECTIONS)})
        completed_llm_calls += 1
        progress(f"Finished bigger_summary for {team}")
        time.sleep(sleep_seconds)

    if progress_callback is not None:
        progress_callback(end_fraction, "Finished all model summaries")

    return pd.DataFrame(summary_rows), pd.DataFrame(bigger_rows)
