# Architecture

Detailed architecture documentation for the Consultation Automation Agent.

## Core Flow (Agent-Driven)

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

## Components

### ConsultPipelineAgent

Located at `src/agent/consult_agent.py`, this is the main agent with 9 MCP tools:

| # | Tool | Purpose |
|---|------|---------|
| 1 | `list_recent_consultation_emails` | Fetch from Gmail |
| 2 | `get_profile_summary` | Load profile |
| 3 | `get_cp_writing_style` | Load writing style guide |
| 4 | `get_application_form_data` | Get form templates |
| 5 | `get_platform_login_info` | Get credentials |
| 6 | `send_email_reply` | Create draft emails |
| 7 | `record_consultation_decision` | Persist decisions |
| 8 | `finalize_run_and_report` | Generate reports |
| 9 | `submit_platform_application` | Browser automation wrapper |

### Data Providers

Located in `src/`:

| Module | Purpose |
|--------|---------|
| `email/` | Gmail API client, email parsing, classification |
| `profile/` | Profile aggregation from static JSON/YAML |
| `platforms/` | Platform detection, form templates (data only) |
| `memory/` | Local JSON persistence (`logs/memory_store.json`) |
| `analytics/` | Metrics tracking and reporting |
| `browser/` | Computer Use implementation (Gemini + Claude) |

### Platforms

Located in `src/platforms/`:

| File | Purpose |
|------|---------|
| `base.py` | Abstract `BasePlatform` interface |
| `glg_platform.py` | GLG platform implementation |
| `guidepoint_platform.py` | Guidepoint platform implementation |
| `coleman_platform.py` | Coleman platform implementation |
| `office_hours_platform.py` | Office Hours platform implementation |
| `registry.py` | Platform routing via `detect_platform()` |

Platforms return form templates; agent handles browser via Computer Use.

## Critical Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point, CLI argument parsing |
| `src/agent/consult_agent.py` | Agent + MCP tools + SYSTEM_PROMPT |
| `src/browser/computer_use.py` | Gemini + Claude Computer Use |
| `src/platforms/registry.py` | Platform routing |
| `src/memory/store.py` | Local JSON persistence |
| `config/config.yaml` | Profile, skills, rates, preferences |
| `config/cp_writing_style.md` | Writing style guide |

## Agent System Prompt

All behavior is defined in `SYSTEM_PROMPT` (`src/agent/consult_agent.py`):

- Decision policies (accept/decline criteria)
- Tool usage guidelines
- Browser interaction instructions
- Safety and failure handling

**To modify agent behavior:** Edit the system prompt, not code.

## Memory Store

- Local JSON: `logs/memory_store.json`
- Auto-deduplication by email ID
- Models in `src/memory/models.py`

## Architecture Principles

### Do

✅ Agentic loop over orchestration  
✅ Tools provide data, not control flow  
✅ System prompt defines behavior  
✅ Computer Use for browser interaction  
✅ Minimal, focused tools (9 operations)

### Don't

❌ No LLM orchestration wrappers  
❌ No custom decision logic in tools  
❌ No workflow coordinators (platforms are data providers)

## Monitoring

- **Logs**: `logs/consultation_*.log` (7-day retention, DEBUG file/INFO console)
- **Reports**: `reports/daily_report_YYYYMMDD.txt` + CSV
- **Metrics**: `python main.py --view-metrics 30`
