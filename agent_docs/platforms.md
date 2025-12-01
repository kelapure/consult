# Platform Integration

Guide for working with consulting platforms and adding new ones.

## Supported Platforms

| Platform | Auth Type | Implementation |
|----------|-----------|----------------|
| GLG | Username/Password | `glg_platform.py` |
| Guidepoint | Username/Password | `guidepoint_platform.py` |
| Coleman | Username/Password | `coleman_platform.py` |
| Office Hours | Google OAuth | `office_hours_platform.py` |

## Credential Pattern

All platforms follow the environment variable pattern:

```bash
{PLATFORM}_USERNAME=your-username
{PLATFORM}_PASSWORD=your-password
{PLATFORM}_LOGIN_URL=https://platform.com/login
{PLATFORM}_DASHBOARD_URL=https://platform.com/dashboard
```

### Examples

```bash
# GLG
GLG_USERNAME=user@example.com
GLG_PASSWORD=secret
GLG_LOGIN_URL=https://glg.it/login
GLG_DASHBOARD_URL=https://glg.it/dashboard

# Guidepoint
GUIDEPOINT_USERNAME=user@example.com
GUIDEPOINT_PASSWORD=secret
GUIDEPOINT_LOGIN_URL=https://guidepoint.com/login
GUIDEPOINT_DASHBOARD_URL=https://guidepoint.com/dashboard

# Coleman
COLEMAN_USERNAME=user@example.com
COLEMAN_PASSWORD=secret
COLEMAN_LOGIN_URL=https://coleman.com/login
COLEMAN_DASHBOARD_URL=https://coleman.com/dashboard

# Office Hours (Google OAuth - no username/password)
OFFICE_HOURS_DASHBOARD_URL=https://officehours.com/home
```

## Adding New Platforms

### Step 1: Create Platform Class

Create a new file in `src/platforms/` inheriting from `BasePlatform`:

```python
from .base import BasePlatform

class NewPlatform(BasePlatform):
    """New consulting platform implementation."""
    
    def __init__(self):
        super().__init__()
        self.name = "new_platform"
    
    def prepare_application(self, email_data: dict, profile: dict) -> dict:
        """Return form template for this platform."""
        return {
            "platform": self.name,
            "form_fields": {
                "expertise": profile.get("expertise", ""),
                "availability": profile.get("availability", ""),
                "rate": profile.get("rate", ""),
                # Platform-specific fields
            },
            "action_url": "https://newplatform.com/apply"
        }
```

### Step 2: Implement prepare_application()

This method returns a form template dict that the agent uses for browser automation:

```python
def prepare_application(self, email_data: dict, profile: dict) -> dict:
    return {
        "platform": "platform_name",
        "form_fields": {
            # Field mappings for the application form
        },
        "action_url": "URL where form submission happens"
    }
```

### Step 3: Register in PlatformRegistry

Edit `src/platforms/registry.py`:

```python
def _register_defaults(self):
    self.register("glg", GLGPlatform())
    self.register("guidepoint", GuidepointPlatform())
    self.register("coleman", ColemanPlatform())
    self.register("office_hours", OfficeHoursPlatform())
    self.register("new_platform", NewPlatform())  # Add this
```

### Step 4: Add Detection Patterns

In `PlatformRegistry.detect_platform()`:

```python
def detect_platform(self, email_content: str) -> Optional[str]:
    patterns = {
        "glg": ["glg.it", "gerson lehrman"],
        "guidepoint": ["guidepoint.com", "guidepoint global"],
        "coleman": ["coleman", "colemanrg"],
        "office_hours": ["officehours.com"],
        "new_platform": ["newplatform.com", "new platform"]  # Add patterns
    }
    # ... detection logic
```

## Platform Design Principles

1. **Data Providers Only**: Platforms return form templates; they don't handle browser interaction
2. **Agent Handles Browser**: Computer Use in `src/browser/computer_use.py` fills forms
3. **No Decision Logic**: Platforms don't decide accept/decline - agent does via system prompt
4. **Stateless**: Each `prepare_application()` call is independent

## Testing Platforms

```bash
# Test specific platform
pytest tests/unit/test_coleman_platform.py -v
pytest tests/unit/test_guidepoint_platform.py -v

# Test platform registry
pytest tests/ -k "platform" -v
```
