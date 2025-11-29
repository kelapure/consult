# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated consultation management system powered by Claude Agent SDK. The agent monitors inbox for consulting opportunities, evaluates them using AI reasoning, and automatically applies to high-fit opportunities via Computer Use. Built with Python 3.13 and Claude Sonnet 4.5.

## Essential Commands

### Development Workflow
```bash
# Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# Run agent
python main.py --days 7           # Process last 7 days of emails
python main.py --report-only      # Generate report only
python main.py --view-metrics 30  # View 30-day metrics
python main.py --view-runs 10     # View last 10 runs
python main.py --headless         # Run browser without UI
python main.py --debug            # Enable debug mode (screenshots, verbose logs)
python main.py --days 7 --headless --debug  # Combine flags
```

### Testing
```bash
# Install test dependencies (if not already installed)
pip install pytest pytest-asyncio pytest-playwright

# Run all tests
pytest tests/ -v

# Run by category
pytest tests/unit/ -v          # Unit tests (fast, isolated)
pytest tests/integration/ -v   # Integration tests (browser, APIs)
pytest tests/e2e/ -v           # End-to-end tests (full pipeline)

# Run specific test files
pytest tests/test_claude_baseline.py -v      # Simple form automation
pytest tests/test_complex_form.py -v         # Complex GLG-like form
pytest tests/test_gemini_baseline.py -v      # Gemini Computer Use

# Unit tests
pytest tests/unit/test_credential_sanitization.py -v
pytest tests/unit/test_cookie_detection.py -v
pytest tests/unit/test_screenshot.py -v
pytest tests/unit/test_browser_lifecycle.py -v
pytest tests/unit/test_claude_parsing.py -v
pytest tests/unit/test_gemini_parsing.py -v

# Integration tests
pytest tests/integration/test_cookie_consent.py -v
pytest tests/integration/test_computer_use_phase3.py -v
pytest tests/integration/test_computer_use_login.py -v

# E2E tests
pytest tests/e2e/test_pipeline.py -v
pytest tests/e2e/test_agent_integration.py -v
pytest tests/e2e/test_benchmark.py -v

# Test individual components without pytest
# Test profile aggregation
python -c "from src.profile.aggregator import ProfileAggregator; import asyncio; asyncio.run(ProfileAggregator().aggregate())"

# Test Gmail connection
python -c "from src.email.gmail_client import GmailClient; GmailClient().authenticate()"
```

### Debugging and Problem Solving
```bash
# View application logs
tail -f logs/consultation_*.log

# Follow logs in real-time
tail -f logs/consultation_*.log | grep ERROR

# Search logs for specific errors
grep "error" logs/consultation_*.log
```

### Cloud Deployment
**Note**: Cloud deployment infrastructure is not currently configured in this repository. The agent runs locally or via Claude Code Web.

## Architecture

### Core Flow (Agent-Driven)
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
│ 5. For Accept:                                         │
│    - Get form template (via MCP tool)                  │
│    - Use Computer Use to fill & submit                 │
│ 6. For Decline:                                        │
│    - Create draft decline email (via MCP tool)         │
│ 7. Record decision (via MCP tool)                      │
│ 8. Generate report (via MCP tool)                      │
└─────────────────────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    ▼                         ▼
┌──────────┐            ┌──────────┐
│ MCP Tools│            │ Computer │
│ (8 tools)│            │   Use    │
└────┬─────┘            └────┬─────┘
     │                       │
     ▼                       ▼
Data Providers        Browser Automation
```

### Key Architectural Principle

**Agent-driven, not orchestrated:**
- Agent makes ALL decisions via system prompt
- Tools provide data, agent determines actions
- No custom orchestration or decision engines
- Computer Use for all browser interaction
- Agent handles the gather→act→verify loop

### Components

**ConsultPipelineAgent** (`src/agent/consult_agent.py`):
- Main agent powered by Claude Agent SDK
- System prompt defines complete behavior and policies
- 8 MCP tools for data access and actions:
  1. `list_recent_consultation_emails` - Fetch emails from Gmail
  2. `get_profile_summary` - Load aggregated profile
  3. `get_cp_writing_style` - Load writing style guide
  4. `get_application_form_data` - Get form templates
  5. `get_platform_login_info` - Get platform credentials
  6. `send_email_reply` - Create draft email responses
  7. `record_consultation_decision` - Persist decisions
  8. `finalize_run_and_report` - Generate reports
- Agent uses Computer Use tool (SDK built-in) for all browser interaction

**Data Providers** (Tools, not orchestration):
- `src/email/` - Gmail API, email parsing, classification
- `src/profile/` - Profile aggregation from static JSON/YAML (no web scraping)
- `src/platforms/` - Platform detection, form templates (data only)
- `src/memory/` - Local JSON persistence for consultation tracking
- `src/analytics/` - Metrics tracking and reporting
- `src/browser/` - Browser automation via Computer Use (Gemini + Claude implementations)

**Platform Abstraction** (`src/platforms/`):
- `base.py` - Abstract interface (1 method: prepare_application)
- `glg_platform.py` - GLG implementation
- `registry.py` - Platform routing via detect_platform()
- **What they provide:** Form templates with field definitions and context
- **What they don't do:** Browser interaction (agent handles via Computer Use)

### Data Flow
```
Gmail API → EmailParser → PlatformRegistry
                ↓
         Agent MCP Tools
                ↓
    ConsultPipelineAgent (Claude SDK)
                ↓
       ┌────────┴────────┐
       ▼                 ▼
  Computer Use      Record to MemoryStore
  (form filling)    (decisions, metrics)
```

## Critical Files

- **`main.py`** - Entry point, calls run_consult_agent()
- **`src/agent/consult_agent.py`** - Main agent with MCP tools and system prompt
- **`src/agent/utils.py`** - Agent utilities
- **`src/browser/computer_use.py`** - Browser automation (Gemini + Claude Computer Use)
- **`src/browser/sanitize.py`** - Credential sanitization for logs
- **`src/browser/cookie_detection.py`** - Cookie consent detection
- **`src/platforms/base.py`** - Platform abstraction (data provider)
- **`src/platforms/glg_platform.py`** - GLG implementation
- **`src/email/processor.py`** - Email processing workflow
- **`src/memory/store.py`** - Local JSON persistence
- **`config/config.yaml`** - Profile, skills, rates, preferences
- **`tests/conftest.py`** - Pytest fixtures and configuration
- **`tests/test_claude_baseline.py`** - Browser automation tests (simple form)
- **`tests/test_complex_form.py`** - Browser automation tests (complex GLG-like form)
- **`tests/test_gemini_baseline.py`** - Gemini Computer Use tests

## Environment Variables

### Required
```bash
ANTHROPIC_API_KEY=sk-ant-xxx  # Claude API key
GMAIL_EMAIL=email@gmail.com   # Gmail address
GOOGLE_API_KEY=AIza-xxx       # Google Gemini API key (for Computer Use)
```

### Optional (Platforms)
```bash
GLG_USERNAME=username         # Required for Computer Use login
GLG_PASSWORD=password         # Required for Computer Use login
GLG_LOGIN_URL=https://glg.it/login
```

### Optional (Configuration)
```bash
DAILY_REPORT_EMAIL=email@gmail.com
```

## Development Patterns

### Adding New Platforms
1. Create class in `src/platforms/` inheriting `BasePlatform`
2. Implement `prepare_application()` method (returns form template)
3. Register in `PlatformRegistry._register_defaults()`
4. Add detection patterns in `PlatformRegistry.detect_platform()`

**Important:** Platforms are data providers only. They return form templates, not workflow logic. The agent handles all browser interaction via Computer Use.

Example:
```python
from src.platforms.base import BasePlatform

class AlphaSightsPlatform(BasePlatform):
    def __init__(self):
        super().__init__('AlphaSights')

    async def prepare_application(self, consultation_data):
        """Return form template for agent to use with Computer Use"""
        return {
            "fields": {
                "introduction": {
                    "type": "textarea",
                    "purpose": "Brief intro of relevant background"
                },
                "availability": {
                    "type": "text",
                    "purpose": "When you're available"
                }
            },
            "context": {
                "project_description": consultation_data.get("project_description", ""),
                "skills_required": consultation_data.get("skills_required", []),
                "profile_context": consultation_data.get("profile_context", {})
            }
        }
```

### Agent System Prompt
All behavior is defined in the system prompt (`SYSTEM_PROMPT` in `consult_agent.py`):
- Decision policies (accept/decline)
- Tool usage guidelines
- Browser interaction instructions (Computer Use)
- Safety and failure handling
- Record-keeping requirements

**To modify agent behavior:** Edit the system prompt, not code.

### MCP Tools
Tools provide data and actions, agent decides when to use them:
- Keep tools simple and focused
- Return structured JSON data
- Tools don't make decisions
- Agent coordinates via system prompt

### Memory Store
- Local JSON storage: `memory_store.json`
- Models in `src/memory/models.py`
- Auto-deduplication by email ID

## File Locations

### Auto-created Directories
- `logs/` - Daily rotated logs (7-day retention)
- `reports/` - Daily reports (TXT + CSV)
- `screenshots/` - Debug screenshots (if enabled)

### Configuration
- `config/config.yaml` - Profile, skills, rates, preferences
- `config/cp_writing_style.md` - Writing style guide
- `profiles/rohit_kelapure_comprehensive_profile.json` - Single profile source
- `.env` - Environment variables (NEVER COMMIT)
- `credentials.json` - Gmail OAuth credentials (NEVER COMMIT, download from GCP)
- `token.pickle` - Gmail OAuth token (NEVER COMMIT, auto-generated)

### Runtime/Cache Files (Auto-generated, gitignored)
- `memory_store.json` - Consultation tracking (local JSON storage)
- `.profile_cache.json` - Profile aggregation cache (24hr TTL)

## Common Pitfalls

### Gmail Authentication
- First run requires OAuth flow (browser popup)
- Creates `token.pickle` automatically
- Re-authenticate: `rm token.pickle && python main.py`
- Production: Use base64-encoded token in `GMAIL_TOKEN_B64`

### Agent Behavior
- All decisions made in agent loop, not custom code
- System prompt is the source of truth
- Don't add decision logic to tools - agent decides
- Tools provide data, agent coordinates

### Platform Implementation
- Platforms are data providers, not workflow coordinators
- Only implement `prepare_application()` method
- Return form templates with field definitions and context
- Agent uses Computer Use for all browser interaction
- Agent gets login credentials via `get_platform_login_info` tool

### Computer Use & Browser Automation
- **Dual implementation**: Gemini 2.5 Computer Use API + Claude Computer Use SDK
- **Primary**: `src/browser/computer_use.py` → `BrowserAutomation.gemini_computer_use()`
  - Uses `gemini-2.5-computer-use-preview-10-2025` model
  - Handles screenshots, mouse, keyboard, scrolling via Gemini API
  - Coordinate normalization (Gemini uses 0-1000, must convert to pixels)
  - Supports form detection, dropdown handling, checkbox interactions
- **Fallback**: `BrowserAutomation.claude_computer_use()` via Agent SDK
- **When to use each**:
  - Gemini: Better for complex forms, multi-step workflows, cost-effective
  - Claude: More reliable for simple tasks, better error messages
- Don't wrap Computer Use in additional custom code
- Screenshot + actions managed by SDK/API
- Failures handled in agent loop with retry logic
- Test fixtures in `tests/fixtures/` for browser automation testing
- Browser runs headless by default (set `headless=False` for debugging)

## Monitoring

### Logs
- Location: `logs/consultation_YYYY-MM-DD.log`
- Rotation: Daily with 7-day retention
- Levels: DEBUG file, INFO console
- View: `tail -f logs/consultation_*.log`

### Reports
- Daily reports: `reports/daily_report_YYYYMMDD.txt`
- CSV data: `reports/daily_report_YYYYMMDD.csv`
- Email delivery if `DAILY_REPORT_EMAIL` set
- Includes: applications, decisions, platform breakdown, strategy metrics

### Metrics
- Real-time via `MetricsTracker`
- Persisted in memory store
- View: `python main.py --view-metrics 30`
- Track: emails processed, decisions made, applications submitted, errors

## Security

- OAuth2 for Gmail (no passwords stored)
- API keys in environment variables only
- `.gitignore` blocks sensitive files
- Local JSON storage for consultation tracking

## Writing Style

All generated content uses CP (Chamath Palihapitiya) writing style from `config/cp_writing_style.md`:
- Direct, confident, no filler words
- Data-driven reasoning
- Professional but conversational
- Applied automatically via system prompt

## Architecture Principles (Claude Agent SDK Best Practices)

This codebase follows Claude Agent SDK best practices:

✅ **Agentic loop over orchestration** - Agent gathers context, makes decisions, iterates
✅ **Tools provide data, not control flow** - MCP tools return data, agent coordinates
✅ **System prompt defines behavior** - All policies in prompt, not code
✅ **Computer Use for browser interaction** - No custom form-filling wrappers
✅ **Context engineering** - Hierarchical data structure, agent searches with tools
✅ **Minimal, focused tools** - 8 primary operations, not exhaustive APIs

❌ **No LLM orchestration wrappers** - Deleted decision engines, content generators
❌ **No multi-strategy fallbacks** - Agent handles Computer Use failures
❌ **No custom decision logic** - Agent reasons via system prompt
❌ **No workflow coordinators** - Platforms are data providers only

## Files Never to Commit

- `.env` - Environment variables with secrets
- `credentials.json` - Gmail OAuth credentials (download from GCP)
- `token.pickle` - Gmail OAuth token (auto-generated)
- `logs/` - Application logs
- `reports/` - Generated reports
- `screenshots/` - Debug screenshots
- `memory_store.json` - Runtime consultation tracking
- `.profile_cache.json` - Profile cache

These are already in `.gitignore`.

## Claude Code Behavioral Rules

**Commit Policy:**
- Never commit without explicit user approval

**Testing Requirements:**
- Always test first - NO SHORTCUTS
- Cannot proceed until tests pass - no workarounds or "efficient paths"
- Always wait for tests to complete
- Must fill all fields during computer use testing

**Development Approach:**
- Research code examples when failing on basic tasks - do research before implementing
- Do NOT overengineer solutions
- After completing tool use tasks, provide a quick summary

**Parallel Tool Calls:**
- Make independent tool calls in parallel (e.g., reading 3 files simultaneously)
- If tool calls have dependencies, run them sequentially
- Never use placeholders or guess missing parameters

**Architecture Integrity:**
- NEVER ask user to manually verify
- All changes must be made in the core agentic loop
- Never create separate python files/scripts outside the defined architecture
- This is a core agentic system - nothing happens outside the agentic loop