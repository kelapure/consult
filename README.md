# Consultation Automation Agent

Automated consultation management system powered by Claude Agent SDK. The agent monitors your inbox for consulting opportunities, evaluates them using AI reasoning, and automatically applies to high-fit opportunities via Computer Use.

## Features

- **Email Monitoring**: Scans Gmail for consultation opportunities from platforms like 
- **AI-Powered Evaluation**: Uses Claude to analyze fit based on your profile, skills, and preferences
- **Automated Applications**: Fills and submits application forms via Computer Use (Gemini + Claude)
- **Smart Decline Drafts**: Creates polite decline emails for low-fit opportunities
- **Decision Tracking**: Persists all decisions with reasoning for future reference
- **Daily Reports**: Generates reports with metrics, decisions, and platform breakdowns

## Architecture

The system follows the **Claude Agent SDK agentic loop** pattern:

```
┌─────────────────────────────────────────────────────────┐
│ ConsultPipelineAgent (Claude Agent SDK)                 │
│ System Prompt defines complete behavior                 │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Agentic Loop: Gather Context → Act → Verify → Repeat   │
├─────────────────────────────────────────────────────────┤
│ 1. List emails (via MCP tool)                          │
│ 2. Get profile summary (via MCP tool)                  │
│ 3. Analyze fit (agent reasoning)                       │
│ 4. Decide: Accept | Decline                            │
│ 5. For Accept: Use Computer Use to fill & submit       │
│ 6. For Decline: Create draft decline email             │
│ 7. Record decision (via MCP tool)                      │
│ 8. Generate report (via MCP tool)                      │
└─────────────────────────────────────────────────────────┘
```

**Key principle:** Agent-driven, not orchestrated. The agent makes ALL decisions via system prompt. Tools provide data, agent determines actions.

## Quick Start

### Prerequisites

- Python 3.12+
- Gmail account with API access
- Anthropic API key
- Google API key (for Gemini Computer Use)

### Installation

```bash
# Clone and setup
git clone <repo-url>
cd consult

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium
```

### Configuration

1. **Environment variables** - Copy `.env.example` to `.env` and fill in:

```bash
ANTHROPIC_API_KEY=sk-ant-xxx      # Claude API key
GMAIL_EMAIL=email@gmail.com       # Gmail address
GOOGLE_API_KEY=AIza-xxx           # Google Gemini API key

# Optional: Platform credentials
GLG_USERNAME=username
GLG_PASSWORD=password
```

2. **Gmail OAuth** - Download `credentials.json` from Google Cloud Console and place in project root.

3. **Profile** - Update `config/config.yaml` with your skills, rates, and preferences.

### Usage

```bash
# Process last 7 days of emails
python main.py --days 7

# Generate report only (no actions)
python main.py --report-only

# View metrics for last 30 days
python main.py --view-metrics 30

# View last 10 runs
python main.py --view-runs 10

# Run headless (no browser UI)
python main.py --headless

# Debug mode (screenshots, verbose logs)
python main.py --debug

# Combine flags
python main.py --days 7 --headless --debug
```

## Project Structure

```
consult/
├── main.py                 # Entry point
├── src/
│   ├── agent/              # ConsultPipelineAgent + MCP tools
│   ├── browser/            # Computer Use (Gemini + Claude)
│   ├── email/              # Gmail API, parsing, classification
│   ├── platforms/          # Platform detection, form templates
│   ├── profile/            # Profile aggregation
│   ├── memory/             # Local JSON persistence
│   └── analytics/          # Metrics and reporting
├── config/
│   ├── config.yaml         # Profile, skills, rates
│   └── cp_writing_style.md # Writing style guide
├── tests/                  # Unit, integration, E2E tests
└── profiles/               # Profile data (JSON)
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run by category
pytest tests/unit/ -v          # Fast, isolated tests
pytest tests/integration/ -v   # Browser, API tests
pytest tests/e2e/ -v           # Full pipeline tests

# Specific test files
pytest tests/test_claude_baseline.py -v      # Simple form automation
pytest tests/test_complex_form.py -v         # Complex GLG-like form
pytest tests/test_gemini_baseline.py -v      # Gemini Computer Use
```

## MCP Tools

The agent has 8 MCP tools for data access and actions:

| Tool | Purpose |
|------|---------|
| `list_recent_consultation_emails` | Fetch emails from Gmail |
| `get_profile_summary` | Load aggregated profile |
| `get_cp_writing_style` | Load writing style guide |
| `get_application_form_data` | Get form templates |
| `get_platform_login_info` | Get platform credentials |
| `send_email_reply` | Create draft email responses |
| `record_consultation_decision` | Persist decisions |
| `finalize_run_and_report` | Generate reports |

## Monitoring

- **Logs**: `logs/consultation_YYYY-MM-DD.log` (7-day retention)
- **Reports**: `reports/daily_report_YYYYMMDD.txt` + CSV
- **Screenshots**: `screenshots/` (debug mode only)
- **Metrics**: `python main.py --view-metrics 30`

## Adding New Platforms

1. Create class in `src/platforms/` inheriting `BasePlatform`
2. Implement `prepare_application()` method (returns form template)
3. Register in `PlatformRegistry._register_defaults()`
4. Add detection patterns in `PlatformRegistry.detect_platform()`

Platforms are data providers only. They return form templates, not workflow logic. The agent handles all browser interaction via Computer Use.

## Security

- OAuth2 for Gmail (no passwords stored)
- API keys in environment variables only
- `.gitignore` blocks sensitive files
- Local JSON storage for consultation tracking

## License

MIT License - see [LICENSE](LICENSE) for details.
