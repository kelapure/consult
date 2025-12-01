# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

Automated consultation agent using Claude Agent SDK. Monitors inbox for consulting opportunities, evaluates them with AI reasoning, and applies via Computer Use. Built with Python 3.13.

## Quick Reference

```bash
# Setup
pip install -r requirements.txt && playwright install chromium

# Run
python main.py --days 7                    # Process last 7 days
python main.py --platform glg              # Specific platform
python main.py --mode dashboard            # Dashboard mode

# Test
pytest tests/ -v                           # All tests
pytest tests/unit/ -v                      # Unit tests (fast)
```

## Architecture

**Agent-driven, not orchestrated.** Tools provide data; agent decides via system prompt.

| File | Purpose |
|------|---------|
| `main.py` | Entry point |
| `src/agent/consult_agent.py` | Agent + 9 MCP tools + SYSTEM_PROMPT |
| `src/browser/computer_use.py` | Gemini + Claude Computer Use |

## Documentation

See `agent_docs/` for detailed documentation:

| File | Contents |
|------|----------|
| `architecture.md` | Components, flow diagrams, design patterns |
| `platforms.md` | Platform integration, adding new platforms |
| `browser_automation.md` | Computer Use implementation details |
| `environment.md` | Environment variables, file locations |
| `common_pitfalls.md` | Debugging and troubleshooting |

## Behavioral Rules

**Commit Policy:** Never commit without explicit user approval

**Testing:**
- Always test first - NO SHORTCUTS
- Cannot proceed until tests pass
- Must fill all fields during computer use testing

**Development:**
- Research before implementing when stuck
- Do NOT overengineer solutions
- Make independent tool calls in parallel
- Never use placeholders or guess parameters

**Architecture Integrity:**
- All changes in the core agentic loop
- Never create separate python files outside defined architecture
- NEVER ask user to manually verify
