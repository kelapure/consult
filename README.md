# Consultation Automation Agent

Automated consultation management system powered by the Claude Agent SDK. The agent monitors Gmail for expert network invitations, evaluates fit with profile-aware reasoning, and uses Gemini + Claude Computer Use to apply or decline on your behalf while keeping detailed metrics and reports.

## Features

- **End-to-end inbox triage** – Classifies and processes GLG, Guidepoint, Coleman, Office Hours, and similar invitations, including automatic archiving once a decision is made.
- **Profile-aware decisioning** – Aggregates skills, rates, and preferences from `config/config.yaml` plus the CP writing guide to keep answers consistent and on-brand.
- **Dual Computer Use stack** – Gemini 2.5 Computer Use (primary) with Claude fallback submits complex vetting forms, supports decline flows, and now includes a batch dashboard mode for processing every invitation in one session.
- **Credential & dashboard helpers** – `get_platform_login_info` standardizes login URLs, dashboard URLs, and credential env vars (and gracefully handles Google OAuth-only platforms).
- **Automated communications** – Generates draft replies/declines, archives processed mail, and records every decision (including submission artifacts) in the local memory store.
- **Observability baked in** – Structured JSON logs, run-level action logs, daily reports, and CLI viewers (`--view-metrics`, `--view-runs`) keep operations auditable.
- **Data-only platform extensions** – Platforms expose form templates + optional prompt builders; the agentic loop always owns orchestration and decision-making.

## Architecture

The system follows the **Claude Agent SDK agentic loop** pattern:

```
┌─────────────────────────────────────────────────────────┐
│ ConsultPipelineAgent (Claude Agent SDK)                 │
│ SYSTEM_PROMPT defines complete behavior                 │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Agentic Loop: Gather Context → Decide → Act → Verify    │
├─────────────────────────────────────────────────────────┤
│ 1. list_recent_consultation_emails                     │
│ 2. get_profile_summary + get_cp_writing_style          │
│ 3. Analyze fit / pick Accept vs Decline                │
│ 4. For Accept:                                         │
│    - get_application_form_data                         │
│    - get_platform_login_info                           │
│    - submit_platform_application (Gemini + Claude)     │
│ 5. For Decline: send_email_reply (draft)               │
│ 6. record_consultation_decision + archive_email        │
│ 7. finalize_run_and_report                             │
└─────────────────────────────────────────────────────────┘
```

**Key principle:** the agent makes **all** decisions via the system prompt. Tools only expose data or side effects; no custom orchestration code lives outside the agent loop.

## Environment & Setup

### Prerequisites

- Python 3.13
- Gmail account with API / OAuth access
- Anthropic API key (`ANTHROPIC_API_KEY`)
- Google Gemini API key (`GOOGLE_API_KEY` or `GEMINI_API_KEY`)
- Playwright with Chromium runtime

### Installation

```bash
git clone <repo-url>
cd consult

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

### Configuration

1. Copy `.env.example` to `.env` and fill the required keys (`ANTHROPIC_API_KEY`, `GMAIL_EMAIL`, `GOOGLE_API_KEY` or `GEMINI_API_KEY`). The template also documents optional flags such as `GEMINI_MAX_EMPTY_RETRIES`, `HEADLESS`, and `DEBUG`.
2. Provide Gmail authentication:
   - **App password** (fastest for dev) via `GMAIL_APP_PASSWORD`, or
   - **OAuth** by placing `credentials.json` in the repo root so the first run can mint `token.pickle`, or
   - Pre-provisioned base64 creds/tokens for hosted deployments.
3. Add platform credentials as needed (`GLG_USERNAME`, `GLG_PASSWORD`, `GLG_LOGIN_URL`, `GLG_DASHBOARD_URL`, etc.). Google OAuth platforms (e.g., Office Hours) only require the dashboard URL.
4. Update `config/config.yaml` with your skills, industry focus, rate cards, and guardrails. Customize `config/cp_writing_style.md` if you want to tweak tone or formatting.
5. (Optional) Load or edit profile JSON under `profiles/` if you maintain multiple personas.

## Usage

### Process recent emails (default email mode)

```bash
# Process the last 7 days of consultation emails
python main.py --days 7
```

### Platform-specific or dashboard runs

```bash
# Focus on a single platform's inbox flow
python main.py --platform glg --days 3

# Batch process every visible invitation on a dashboard (requires --platform)
python main.py --mode dashboard --platform office_hours
```

Dashboard mode keeps one browser session open, calls `submit_platform_application` with `form_data.mode = "batch_dashboard"`, and uses Google OAuth automatically when applicable.

### Reporting, metrics, and diagnostics

```bash
# Produce a daily report without processing new mail
python main.py --report-only

# Inspect aggregated metrics for the last 30 days
python main.py --view-metrics 30

# Inspect the last 10 recorded runs (timestamps, outcomes, durations)
python main.py --view-runs 10
```

### Helpful flags

- `--headless` sets `HEADLESS=true` (no browser UI, ideal for CI/cloud).
- `--debug` enables verbose logging, richer console output, and saves screenshots under `screenshots/`.
- Combine any of the flags above (e.g., `python main.py --days 7 --platform glg --headless --debug`).

## Project Structure

```
.
├── main.py                          # CLI entry point / argparse
├── config/
│   ├── config.yaml                  # Profile, rates, preferences
│   └── cp_writing_style.md          # Narrative guardrails
├── src/
│   ├── agent/                       # ConsultPipelineAgent + MCP tools
│   ├── analytics/                   # Metrics tracker + reporter
│   ├── browser/                     # Gemini + Claude Computer Use helpers
│   ├── email/                       # Gmail client, parser, processor
│   ├── memory/                      # Local JSON persistence
│   ├── platforms/                   # Base + GLG/Guidepoint/Coleman/OH providers
│   ├── profile/                     # Aggregator utilities
│   └── utils.py
├── scripts/                         # Operational helpers
│   ├── archive_glg_sample.py
│   ├── archive_processed_emails.py
│   ├── delete_newsletter_emails.py
│   ├── list_archived_glg.py
│   ├── setup_browser_profile.py
│   ├── unarchive_glg_emails.py
│   └── verify_login_session.py
├── tests/
│   ├── unit/                        # Fast coverage (parsers, stores, etc.)
│   ├── integration/                 # Browser/API focused suites
│   └── e2e/                         # Full agent loop benchmarks
├── profiles/                        # Persona definitions (gitignored in prod)
├── test_results/                    # Benchmark outputs (reference only)
├── requirements.txt
├── README.md
└── logs/, reports/, screenshots/    # Generated at runtime (gitignored)
```

## Testing

```bash
# Full suite (slowest, but mirrors CI)
pytest tests/ -v

# Targeted suites
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -v

# Useful spot checks
pytest tests/integration/test_cookie_consent.py -v
pytest tests/unit/test_archive_email.py::test_archive_email_happy_path -v
pytest tests/e2e/test_agent_integration.py -v
```

Run tests locally whenever you modify code, and surface failures with their stdout/stderr when sharing results.

## MCP Tools

| Tool | Purpose |
| --- | --- |
| `list_recent_consultation_emails` | Query Gmail (via `EmailProcessor`) for the most recent invitations, returning structured JSON for downstream reasoning. |
| `get_cp_writing_style` | Load the CP writing style guide so drafted answers and decline emails stay on brand. |
| `get_profile_summary` | Aggregate the consultant profile (skills, rates, preferences) from config + profile data. |
| `record_consultation_decision` | Persist accept/decline decisions, reasoning, and submission metadata to the memory store and metrics tracker. |
| `archive_email` | Remove processed invitations from the inbox and mark them as processed. |
| `finalize_run_and_report` | Flush metrics, generate the daily report, and (optionally) email it. |
| `get_application_form_data` | Ask the platform data provider for the correct form template + contextual payload. |
| `get_platform_login_info` | Return login URLs, dashboard URLs, and credentials (or indicate Google OAuth) from env vars. |
| `send_email_reply` | Draft a Gmail response (e.g., decline) for later review before sending. |
| `submit_platform_application` | Execute Computer Use flows (Gemini primary, Claude fallback) to submit or decline opportunities, including the new `batch_dashboard` processing mode. |

## Monitoring & Run Artifacts

- **Structured logs** – `logs/consultation_json_{timestamp}.log` stores JSON logs with correlation IDs for each run.
- **Action logs** – `logs/runs/*.json` capture browser actions taken by `submit_platform_application` (including dashboard batches).
- **Daily reports** – Generated under `reports/daily_report_YYYYMMDD.txt` (plus CSV variants) whenever `finalize_run_and_report` runs.
- **Memory store** – `logs/memory_store.json` tracks per-email decisions, enabling `--view-metrics` and `--view-runs`.
- **Screenshots** – Saved to `screenshots/` when `--debug` is enabled, useful for verifying browser automation.
- **Benchmark outputs** – `test_results/benchmark_*.txt` capture historical performance snapshots.

## Adding New Platforms

1. Create a class in `src/platforms/` that inherits `BasePlatform`.
2. Implement `prepare_application()` to return the structured form template (no orchestration logic).
3. Optionally implement helpers like `build_task_prompt()` or `get_platform_config()` for richer Computer Use instructions.
4. Register the platform in `PlatformRegistry._register_defaults()` and add detection patterns in `PlatformRegistry.detect_platform()`.
5. Keep platform classes data-only—ConsultPipelineAgent remains the single place where decisions are made.

## Security

- Gmail access uses OAuth tokens or app passwords stored outside Git; `.env`, `credentials.json`, `token.pickle`, and profile caches are gitignored.
- All API keys live in environment variables; never hard-code secrets in source.
- Logs redact sensitive content and rotate daily (`logs/consultation_json_{time}.log` keeps seven days).
- Local persistence stays under `logs/` and can be purged if you need to re-authenticate.

## License

MIT License – see [LICENSE](LICENSE) for the full text.
