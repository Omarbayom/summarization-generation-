from __future__ import annotations

import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Iterable


def send_email_with_attachments(cfg: Dict[str, Any], attachments: Iterable[str]) -> bool:
    email_cfg = cfg.get("email", {})
    required = ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "email_from", "email_to"]
    missing = [name for name in required if not email_cfg.get(name)]
    if missing:
        raise ValueError(f"Missing email settings: {missing}")

    msg = EmailMessage()
    msg["From"] = email_cfg["email_from"]
    msg["To"] = email_cfg["email_to"]
    msg["Subject"] = email_cfg.get("subject", "Monthly Summary Reports")
    msg.set_content(email_cfg.get("body", "Attached are the summary and bigger summary reports."))

    for path in attachments:
        path_obj = Path(path)
        ctype, encoding = mimetypes.guess_type(path_obj)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        with path_obj.open("rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=path_obj.name)

    with smtplib.SMTP(email_cfg["smtp_host"], int(email_cfg["smtp_port"])) as server:
        server.starttls()
        server.login(email_cfg["smtp_user"], email_cfg["smtp_password"])
        server.send_message(msg)
    return True
