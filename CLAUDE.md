# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated consultation management system powered by Claude Agent SDK. The agent monitors inbox for consulting opportunities, evaluates them using AI reasoning, and automatically applies to high-fit opportunities via Computer Use. Built with Python 3.13.

## Essential Commands

### Setup
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Run Agent
```bash
python main.py --days 7                       # Process last 7 days of emails
python main.py --platform glg                 # Process specific platform (glg|guidepoint|coleman|office_hours)
python main.py --mode dashboard --platform office_hours  # Batch process ALL invitations on dashboard
python main.py --headless --debug             # Headless with debug screenshots
python main.py --report-only                  # Generate report only
python main.py --view-metrics 30              # View 30-day metrics
python main.py --view-runs 10                 # View last 10 runs
```

### Testing
```bash
pytest tests/ -v                              # All tests
pytest tests/unit/ -v                         # Unit tests (fast)
pytest tests/integration/ -v                  # Browser/API tests
pytest tests/e2e/ -v                          # Full pipeline tests
pytest tests/test_complex_form.py -v          # GLG-like form test
pytest tests/unit/test_cookie_detection.py::test_function_name -v  # Single test
```

### Debug Commands
```bash
tail -f logs/consultation_*.log               # Follow logs
python -c "from src.profile.aggregator import ProfileAggregator; import asyncio; asyncio.run(ProfileAggregator().aggregate())"
python -c "from src.email.gmail_client import GmailClient; GmailClient().authenticate()"
```

## Architecture

### Core Flow (Agent-Driven)
```
ConsultPipelineAgent (Claude Agent SDK)
         │ System prompt defines ALL behavior
         ▼
Agentic Loop: Gather Context → Decide → Act → Verify → Repeat
         │
    ┌────┴────┐
    ▼         ▼
MCP Tools   Computer Use
(9 tools)   (Browser)
    │         │
    ▼         ▼
Data       Form Filling
Providers  & Submission
```

**Key principle:** Agent-driven, not orchestrated. Tools provide data; agent makes decisions via system prompt. No custom orchestration code.

### Components

**ConsultPipelineAgent** (`src/agent/consult_agent.py`):
- Main agent with 9 MCP tools:
  1. `list_recent_consultation_emails` - Fetch from Gmail
  2. `get_profile_summary` - Load profile
  3. `get_cp_writing_style` - Load writing style guide
  4. `get_application_form_data` - Get form templates
  5. `get_platform_login_info` - Get credentials
  6. `send_email_reply` - Create draft emails
  7. `record_consultation_decision` - Persist decisions
  8. `finalize_run_and_report` - Generate reports
  9. `submit_platform_application` - Browser automation wrapper

**Data Providers** (`src/`):
- `email/` - Gmail API client, email parsing, classification
- `profile/` - Profile aggregation from static JSON/YAML
- `platforms/` - Platform detection, form templates (data only)
- `memory/` - Local JSON persistence (`logs/memory_store.json`)
- `analytics/` - Metrics tracking and reporting
- `browser/` - Computer Use implementation (Gemini + Claude)

**Platforms** (`src/platforms/`):
- `base.py` - Abstract `BasePlatform` interface
- `glg_platform.py`, `guidepoint_platform.py`, `coleman_platform.py`, `office_hours_platform.py`
- `registry.py` - Platform routing via `detect_platform()`
- Platforms return form templates; agent handles browser via Computer Use

## Critical Files

- `main.py` - Entry point, CLI argument parsing
- `src/agent/consult_agent.py` - Agent + MCP tools + SYSTEM_PROMPT (defines ALL behavior)
- `src/browser/computer_use.py` - Gemini + Claude Computer Use implementation
- `src/platforms/registry.py` - Platform routing via `detect_platform()`
- `src/memory/store.py` - Local JSON persistence
- `config/config.yaml` - Profile, skills, rates, preferences
- `config/cp_writing_style.md` - Writing style guide for generated content

## Environment Variables

### Required
```bash
ANTHROPIC_API_KEY=sk-ant-xxx      # Claude API
GMAIL_EMAIL=email@gmail.com       # Gmail address
GOOGLE_API_KEY=AIza-xxx           # Gemini Computer Use API
```

### Platform Credentials (env pattern: `{PLATFORM}_USERNAME`, `{PLATFORM}_PASSWORD`, `{PLATFORM}_LOGIN_URL`, `{PLATFORM}_DASHBOARD_URL`)
```bash
GLG_USERNAME=xxx                  GLG_PASSWORD=xxx
GUIDEPOINT_USERNAME=xxx           GUIDEPOINT_PASSWORD=xxx
COLEMAN_USERNAME=xxx              COLEMAN_PASSWORD=xxx
# Office Hours uses Google OAuth (no username/password needed)
OFFICE_HOURS_DASHBOARD_URL=https://officehours.com/home
```

## Development Patterns

### Adding New Platforms
1. Create class in `src/platforms/` inheriting `BasePlatform`
2. Implement `prepare_application()` → returns form template dict
3. Register in `PlatformRegistry._register_defaults()`
4. Add detection patterns in `PlatformRegistry.detect_platform()`

Platforms are **data providers only**. They return form templates; agent handles browser via Computer Use.

### Agent System Prompt
All behavior is defined in `SYSTEM_PROMPT` (`src/agent/consult_agent.py`):
- Decision policies (accept/decline criteria)
- Tool usage guidelines
- Browser interaction instructions
- Safety and failure handling

**To modify agent behavior:** Edit the system prompt, not code.

### Memory Store
- Local JSON: `logs/memory_store.json`
- Auto-deduplication by email ID
- Models in `src/memory/models.py`

## File Locations

**Auto-created:** `logs/`, `reports/`, `screenshots/` (debug only)

**Configuration:**
- `config/config.yaml` - Profile, skills, rates
- `config/cp_writing_style.md` - Writing style guide
- `.env` - Environment variables (NEVER COMMIT)
- `credentials.json` - Gmail OAuth (download from GCP, NEVER COMMIT)
- `token.pickle` - Gmail OAuth token (auto-generated, NEVER COMMIT)

**Runtime (gitignored):** `logs/memory_store.json`, `logs/processed_emails.json`, `.profile_cache.json`

## Common Pitfalls

### Gmail Authentication
- First run requires OAuth flow (browser popup) → creates `token.pickle`
- Re-authenticate: `rm token.pickle && python main.py`

### Computer Use & Browser Automation
- **Dual implementation**: Gemini 2.5 (`gemini-2.5-computer-use-preview-10-2025`) + Claude Computer Use
- Primary: Gemini (better for complex forms, cost-effective)
- Fallback: Claude (more reliable for simple tasks)
- Coordinate normalization: Gemini uses 0-1000, convert to pixels
- Browser headless by default; use `--debug` for screenshots

### Agent Architecture Rules
- All decisions via system prompt, not custom code
- Tools provide data; agent coordinates
- Don't add decision logic to tools
- Platforms are data providers only (return form templates)

## Monitoring

- **Logs**: `logs/consultation_*.log` (7-day retention, DEBUG file/INFO console)
- **Reports**: `reports/daily_report_YYYYMMDD.txt` + CSV
- **Metrics**: `python main.py --view-metrics 30`

## Architecture Principles

✅ Agentic loop over orchestration
✅ Tools provide data, not control flow
✅ System prompt defines behavior
✅ Computer Use for browser interaction
✅ Minimal, focused tools (9 operations)

❌ No LLM orchestration wrappers
❌ No custom decision logic
❌ No workflow coordinators (platforms are data providers)

## Claude Code Behavioral Rules

**Commit Policy:** Never commit without explicit user approval

**Testing Requirements:**
- Always test first - NO SHORTCUTS
- Cannot proceed until tests pass
- Must fill all fields during computer use testing

**Development Approach:**
- Research before implementing when stuck
- Do NOT overengineer solutions
- Make independent tool calls in parallel
- Never use placeholders or guess parameters

**Architecture Integrity:**
- All changes in the core agentic loop
- Never create separate python files outside defined architecture
- NEVER ask user to manually verify