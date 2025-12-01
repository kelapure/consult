# Browser Automation & Computer Use

Documentation for the dual-implementation browser automation system.

## Overview

The system uses a dual implementation for browser automation:

| Provider | Model | Use Case |
|----------|-------|----------|
| **Primary** | Gemini 2.5 (`gemini-2.5-computer-use-preview-10-2025`) | Complex forms, cost-effective |
| **Fallback** | Claude Computer Use | Simple tasks, higher reliability |

Implementation: `src/browser/computer_use.py`

## Architecture

```
Agent (submit_platform_application tool)
         │
         ▼
Computer Use Module
         │
    ┌────┴────┐
    ▼         ▼
Gemini 2.5  Claude
(Primary)   (Fallback)
    │         │
    └────┬────┘
         ▼
   Playwright Browser
         │
         ▼
   Platform Forms
```

## Coordinate Systems

### Gemini

- Uses normalized coordinates: 0-1000 range
- Must convert to actual pixels before browser interaction

```python
# Gemini returns normalized coordinates
gemini_x, gemini_y = 500, 300  # 0-1000 range

# Convert to pixels
viewport_width, viewport_height = 1920, 1080
actual_x = (gemini_x / 1000) * viewport_width
actual_y = (gemini_y / 1000) * viewport_height
```

### Claude

- Uses actual pixel coordinates
- No conversion needed

## Browser Configuration

### Headless Mode (Default)

```bash
python main.py --headless  # Run without visible browser
```

### Debug Mode

```bash
python main.py --debug  # Enables debug screenshots
```

Debug screenshots saved to: `screenshots/`

## Key Functions

### submit_platform_application

MCP tool in `src/agent/consult_agent.py` that wraps Computer Use:

```python
async def submit_platform_application(args: Dict[str, Any]) -> Dict[str, Any]:
    """Submit application via browser automation."""
    platform = args.get("platform")
    form_data = args.get("form_data")
    
    # Delegates to Computer Use module
    result = await computer_use.submit_form(platform, form_data)
    return result
```

### Browser Lifecycle

1. **Launch**: Playwright creates browser instance
2. **Navigate**: Go to platform login page
3. **Authenticate**: Fill login form
4. **Navigate**: Go to application form
5. **Fill**: Enter form data from platform template
6. **Submit**: Click submit button
7. **Verify**: Check for success indicators
8. **Cleanup**: Close browser

## Supported Actions

| Action | Description |
|--------|-------------|
| `click` | Click at coordinates |
| `type` | Type text into focused element |
| `scroll` | Scroll page |
| `screenshot` | Capture current state |
| `wait` | Wait for element/condition |

## Error Handling

### Common Failures

| Error | Cause | Resolution |
|-------|-------|------------|
| Coordinate mismatch | Wrong resolution | Verify viewport size |
| Element not found | Page structure changed | Update selectors |
| Timeout | Slow network | Increase timeout |
| Auth failure | Invalid credentials | Check platform credentials |

### Retry Strategy

```python
# Built-in retry with exponential backoff
MAX_RETRIES = 3
RETRY_DELAY = [1, 2, 4]  # seconds
```

## Cookie Consent

Cookie detection and handling in `src/browser/cookie_detection.py`:

- Automatically detects cookie consent dialogs
- Clicks "Accept" or "OK" buttons
- Handles various consent frameworks

## Testing Browser Automation

```bash
# Test login flow
pytest tests/integration/test_computer_use_login.py -v

# Test complex forms
pytest tests/test_complex_form.py -v

# Test cookie consent handling
pytest tests/integration/test_cookie_consent.py -v

# Full pipeline test
pytest tests/e2e/test_pipeline.py -v
```

## Debug Commands

```bash
# Watch screenshots being generated
ls -la screenshots/

# View browser logs
tail -f logs/consultation_*.log | grep -i browser

# Test with visible browser (no headless)
python main.py --platform glg --debug
```

## Environment Variables

```bash
GOOGLE_API_KEY=AIza-xxx  # Required for Gemini Computer Use
ANTHROPIC_API_KEY=sk-ant-xxx  # Required for Claude fallback
```
