from __future__ import annotations

import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any

import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent / "src"))

from monthly_summary.config import load_config
from monthly_summary.emailer import send_email_with_attachments
from monthly_summary.pipeline import run_pipeline

load_dotenv()

st.set_page_config(page_title="Monthly XLSX Summary Generator", page_icon="📄", layout="wide")


EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def load_optional_streamlit_secrets() -> None:
    """Allows Streamlit Cloud secrets, but local .env works without secrets.toml."""
    try:
        for key, value in dict(st.secrets).items():
            os.environ.setdefault(str(key), str(value))
    except Exception:
        return


load_optional_streamlit_secrets()


def is_valid_email(email: str) -> bool:
    email = (email or "").strip()
    if not email or len(email) > 254:
        return False
    if ".." in email:
        return False
    return bool(EMAIL_RE.fullmatch(email))


def format_seconds(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def env_first(env_name: str, fallback: Any = "") -> Any:
    value = os.getenv(env_name)
    if value is None or value == "":
        return fallback
    return value


def build_email_config(recipient_email: str) -> Dict[str, Any]:
    """Build email config from config.yaml plus .env / Streamlit Secrets."""
    cfg = load_config("config.yaml")
    email_cfg = dict(cfg.get("email", {}))

    smtp_user = env_first("SMTP_USER", email_cfg.get("smtp_user", ""))
    email_from = env_first("EMAIL_FROM", email_cfg.get("email_from", smtp_user))

    email_cfg.update(
        {
            "enabled": True,
            "smtp_host": env_first("SMTP_HOST", email_cfg.get("smtp_host", "smtp.gmail.com")),
            "smtp_port": int(env_first("SMTP_PORT", email_cfg.get("smtp_port", 587))),
            "smtp_user": smtp_user,
            "smtp_password": env_first("SMTP_PASSWORD", email_cfg.get("smtp_password", "")),
            "email_from": email_from,
            "email_to": recipient_email.strip(),
            "subject": email_cfg.get("subject") or "Monthly Summary Reports",
            "body": email_cfg.get("body") or "Attached are the summary and bigger summary reports.",
        }
    )
    cfg["email"] = email_cfg
    return cfg


def show_downloads(paths: Dict[str, str]) -> None:
    st.subheader("Downloads")
    for _, path in paths.items():
        path_obj = Path(path)
        if not path_obj.exists():
            continue
        with path_obj.open("rb") as f:
            st.download_button(
                label=f"Download {path_obj.name}",
                data=f.read(),
                file_name=path_obj.name,
                mime="application/octet-stream",
            )


st.title("Monthly XLSX Summary Generator")
st.caption("Upload the XLSX, enter the recipient email, then generate and send the reports.")

cfg_preview = load_config("config.yaml")
default_email = (
    os.getenv("EMAIL_TO")
    or str(cfg_preview.get("email", {}).get("email_to", "")).strip()
    or "omarbayom3006@gmail.com"
)
output_dir = str(cfg_preview.get("project", {}).get("output_dir", "outputs"))

uploaded = st.file_uploader("Upload monthly/daily meeting XLSX", type=["xlsx"])
recipient_email = st.text_input("Recipient email (required)", value=default_email)
email_ok = is_valid_email(recipient_email)

if recipient_email and not email_ok:
    st.warning("The email format is invalid. Reports will still be generated and download buttons will appear, but email will not be sent.")
elif not recipient_email:
    st.warning("Recipient email is required. Reports can still be generated for download, but email will not be sent until a valid email is entered.")

if uploaded and st.button("Generate and send reports", type="primary"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded.read())
        input_path = tmp.name

    # Email is intentionally disabled during pipeline execution so SMTP failure never blocks downloads.
    overrides = {
        "project": {"output_dir": output_dir},
        "email": {"enabled": False},
        "pdf": {"one_team_per_page": False},
    }

    progress_bar = st.progress(0, text="Starting...")
    progress_box = st.empty()
    started_at = time.monotonic()

    def update_progress(fraction: float, message: str) -> None:
        fraction = max(0.0, min(1.0, float(fraction)))
        elapsed = time.monotonic() - started_at
        remaining = ((elapsed / fraction) - elapsed) if fraction >= 0.03 else None
        percent = int(round(fraction * 100))
        eta = format_seconds(remaining) if remaining is not None else "estimating..."
        progress_bar.progress(percent, text=f"{percent}% — {message}")
        progress_box.info(
            f"**Current step:** {message}  \n"
            f"**Elapsed:** {format_seconds(elapsed)}  \n"
            f"**Estimated remaining:** {eta}"
        )

    try:
        summary_df, bigger_df, paths = run_pipeline(
            input_path,
            config_path="config.yaml",
            overrides=overrides,
            progress_callback=update_progress,
        )
    except Exception as exc:  # noqa: BLE001
        progress_bar.empty()
        progress_box.empty()
        st.error(str(exc))
        st.info(
            "If extraction failed, open config.yaml and check the markers: category_header, start_marker, "
            "end_markers, blockers_marker, and support_marker."
        )
    else:
        update_progress(1.0, "Reports generated")
        st.success("Reports generated successfully")

        if email_ok:
            try:
                email_cfg = build_email_config(recipient_email)
                send_email_with_attachments(
                    email_cfg,
                    [paths["xlsx"], paths["summary_pdf"], paths["bigger_summary_pdf"]],
                )
                st.success(f"Email sent to {recipient_email.strip()}")
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Email was not sent: {exc}")
                st.info("Download buttons are available below.")
        else:
            st.warning("Email was not sent because the recipient email is invalid or empty.")

        # Downloads always appear after successful generation, even when email was sent.
        show_downloads(paths)

        with st.expander("Preview generated tables"):
            tab1, tab2 = st.tabs(["summary", "bigger_summary"])
            with tab1:
                st.dataframe(summary_df, use_container_width=True)
            with tab2:
                st.dataframe(bigger_df, use_container_width=True)
else:
    st.info("Upload an XLSX file and enter the recipient email to start.")
