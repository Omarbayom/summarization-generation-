from __future__ import annotations

import json

REQUIRED_SECTIONS = [
    "Executive Overview",
    "Key Completed Work",
    "Ongoing / In Progress",
    "Pending / Risks",
]

EMPTY_SECTION_FALLBACKS = {
    "Executive Overview": "No clear executive overview could be derived from the provided source notes.",
    "Key Completed Work": "No completed work is clearly identified from the provided source notes.",
    "Ongoing / In Progress": "No ongoing work is clearly identified from the provided source notes.",
    "Pending / Risks": "No major pending risks are clearly identified from the provided source notes.",
}

JSON_SCHEMA_EXAMPLE = json.dumps(
    {
        "Executive Overview": ["bullet 1", "bullet 2"],
        "Key Completed Work": ["bullet 1", "bullet 2"],
        "Ongoing / In Progress": ["bullet 1", "bullet 2"],
        "Pending / Risks": ["bullet 1", "bullet 2"],
    },
    ensure_ascii=False,
)

SUMMARY_SYSTEM_PROMPT = f"""
You are an executive PMO summarizer for engineering weekly/monthly status reports.

Return ONLY valid JSON.
No markdown, no code fences, no comments, no bullet symbols, and no extra keys.
Use exactly these keys: {', '.join(REQUIRED_SECTIONS)}.
Each value must be an array of concise bullet strings.

Accuracy rules:
- Summarize only what is supported by the provided source notes.
- Do not invent tasks, risks, dates, names, device IDs, percentages, standards, CAR numbers, or decisions.
- Do not upgrade task status. If an item is ongoing, pending, under review, awaiting approval, or being investigated, keep it out of "Key Completed Work".
- Put an item in "Key Completed Work" only when the source clearly says it is completed, finalized, approved, submitted, done, closed, verified, issued, generated, delivered, held, conducted, or reviewed.
- Put uncertain, awaiting, under-review, blocked, delayed, or dependency items in "Pending / Risks".
- If the source does not clearly identify information for a section, use the section-specific fallback sentence.
- Do not add external PM assumptions such as audit risk, certification delay, resource shortage, or schedule impact unless the source clearly supports it.
- Preserve important names, CAR numbers, device IDs, versions, standards, counts, and percentages exactly when present.
- Use simple ASCII hyphen '-' instead of special Unicode dashes.
- Avoid words that imply completion unless completion is clearly stated in the source.

Output JSON example: {JSON_SCHEMA_EXAMPLE}
""".strip()

SUMMARY_USER_TEMPLATE = """
Team: {team}
Report style: {report_style_name}

Input grouped meeting notes:
{team_input}

Create a compact executive summary for this team in the configured report style.

Rules:
- Return only JSON using the required four keys.
- No markdown symbols such as **, #, -, or bullet characters at the start of strings.
- Executive Overview: 1 to 2 bullets.
- Key Completed Work: 4 to 7 bullets.
- Ongoing / In Progress: 3 to 6 bullets.
- Pending / Risks: 2 to 5 bullets.
- Remove duplicate items and merge repeated meetings.
- Keep the original task status from the source notes.
- Do not move ongoing, pending, under-review, awaiting, or investigation items into completed work.
- Do not create Management Attention or any extra section.
- If no clear pending risks exist, write: "No major pending risks are clearly identified from the provided source notes."
""".strip()

BIGGER_SUMMARY_SYSTEM_PROMPT = SUMMARY_SYSTEM_PROMPT

BIGGER_SUMMARY_USER_TEMPLATE = """
Team: {team}
Report style: {report_style_name}

Input grouped meeting notes:
{team_input}

Create a bigger but still executive-style summary for this team in the configured report style.

Rules:
- Return only JSON using the required four keys.
- No markdown symbols such as **, #, -, or bullet characters at the start of strings.
- Executive Overview: 2 to 4 bullets.
- Key Completed Work: 6 to 12 bullets, grouped and specific.
- Ongoing / In Progress: 5 to 10 bullets, with useful details.
- Pending / Risks: 4 to 8 bullets, focused only on blockers, dependencies, risks, pending approvals, unfinished work, and unclear ownership explicitly supported by the source notes.
- Merge duplicate notes instead of copying raw lines.
- Preserve important names, CAR numbers, device IDs, versions, standards, counts, and percentages exactly when present.
- Keep the original task status from the source notes.
- Do not move ongoing, pending, under-review, awaiting, or investigation items into completed work.
- Do not infer business impact unless the source states it or it is directly obvious from a stated blocker.
- Do not create Management Attention or any extra section.
- If no clear pending risks exist, write: "No major pending risks are clearly identified from the provided source notes."
""".strip()


def build_summary_prompt(
    team: str,
    team_input: str,
    report_style_name: str = "configured executive report style",
) -> str:
    return SUMMARY_USER_TEMPLATE.format(
        team=team,
        team_input=team_input,
        report_style_name=report_style_name,
    )


def build_bigger_summary_prompt(
    team: str,
    team_input: str,
    report_style_name: str = "configured executive report style",
) -> str:
    return BIGGER_SUMMARY_USER_TEMPLATE.format(
        team=team,
        team_input=team_input,
        report_style_name=report_style_name,
    )


def fallback_section_text(section: str) -> str:
    return EMPTY_SECTION_FALLBACKS.get(
        section,
        "No clear information is identified from the provided source notes.",
    )
