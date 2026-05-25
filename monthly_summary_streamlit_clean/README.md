# Monthly XLSX Summary Generator — Streamlit Only

This version is cleaned for Streamlit use only. It generates only:

- `summary`
- `bigger_summary`
- `summary_may26_style.pdf`
- `bigger_summary_may26_style.pdf`
- `summary_and_bigger_summary.xlsx`

## What was fixed

- Model output is forced into JSON instead of markdown.
- PDF text is normalized to remove black-square/bad Unicode issues.
- Output token limits are increased to reduce cut-off summaries.
- Every team is validated to contain the four May26 sections before export.
- PDF uses continuous page flow instead of starting every team on a new page.
- PDF uses Times/serif styling and removes the extra horizontal line.
- `Management Attention` was removed to match May26 style.
- Non-Streamlit files were removed.

## Run locally

Create your own `.env` beside `app.py`, then run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Example `.env`:

```env
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=your_key_here

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_digit_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=manager@company.com
```

## Important config

Edit `config.yaml` if your Excel layout markers are different.

Main model settings:

```yaml
llm:
  provider: ollama
  base_url: ${OLLAMA_BASE_URL:-https://ollama.com}
  summary_model: gpt-oss:120b-cloud
  bigger_summary_model: gpt-oss:120b-cloud
```

Use `provider: offline` only to test the UI without calling a model.
