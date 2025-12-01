# Environment & Configuration

Complete reference for environment variables and file locations.

## Required Environment Variables

These must be set for the system to function:

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-xxx` |
| `GMAIL_EMAIL` | Gmail address for monitoring | `user@gmail.com` |
| `GOOGLE_API_KEY` | Gemini Computer Use API | `AIza-xxx` |

## Platform Credentials

Pattern: `{PLATFORM}_USERNAME`, `{PLATFORM}_PASSWORD`, `{PLATFORM}_LOGIN_URL`, `{PLATFORM}_DASHBOARD_URL`

### GLG

```bash
GLG_USERNAME=user@example.com
GLG_PASSWORD=your-password
GLG_LOGIN_URL=https://glg.it/login
GLG_DASHBOARD_URL=https://glg.it/dashboard
```

### Guidepoint

```bash
GUIDEPOINT_USERNAME=user@example.com
GUIDEPOINT_PASSWORD=your-password
GUIDEPOINT_LOGIN_URL=https://guidepoint.com/login
GUIDEPOINT_DASHBOARD_URL=https://guidepoint.com/dashboard
```

### Coleman

```bash
COLEMAN_USERNAME=user@example.com
COLEMAN_PASSWORD=your-password
COLEMAN_LOGIN_URL=https://coleman.com/login
COLEMAN_DASHBOARD_URL=https://coleman.com/dashboard
```

### Office Hours (Google OAuth)

```bash
# No username/password needed - uses Google OAuth
OFFICE_HOURS_DASHBOARD_URL=https://officehours.com/home
```

## Configuration Files

### Project Configuration

| File | Purpose | Commit? |
|------|---------|---------|
| `config/config.yaml` | Profile, skills, rates, preferences | ✅ Yes |
| `config/cp_writing_style.md` | Writing style guide for generated content | ✅ Yes |
| `.env` | Environment variables | ❌ Never |
| `.env.example` | Template for environment variables | ✅ Yes |

### Gmail OAuth

| File | Purpose | Commit? |
|------|---------|---------|
| `credentials.json` | Gmail OAuth app credentials (download from GCP) | ❌ Never |
| `token.pickle` | Gmail OAuth token (auto-generated) | ❌ Never |

## File Locations

### Auto-Created Directories

| Directory | Purpose |
|-----------|---------|
| `logs/` | Application logs |
| `reports/` | Generated reports |
| `screenshots/` | Debug screenshots (only with `--debug`) |

### Runtime Files (gitignored)

| File | Purpose |
|------|---------|
| `logs/memory_store.json` | Persistent memory storage |
| `logs/processed_emails.json` | Tracking processed emails |
| `.profile_cache.json` | Cached profile data |

### Log Files

| Pattern | Retention | Level |
|---------|-----------|-------|
| `logs/consultation_*.log` | 7 days | DEBUG (file) |
| Console | N/A | INFO |

## Setting Up Environment

### Step 1: Copy Template

```bash
cp .env.example .env
```

### Step 2: Edit .env

Add your credentials:

```bash
# Core (required)
ANTHROPIC_API_KEY=sk-ant-xxx
GMAIL_EMAIL=your-email@gmail.com
GOOGLE_API_KEY=AIza-xxx

# Platforms (as needed)
GLG_USERNAME=xxx
GLG_PASSWORD=xxx
# ... etc
```

### Step 3: Gmail Setup

1. Create project in Google Cloud Console
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download as `credentials.json` to project root
5. First run will open browser for OAuth flow

## Validation

Debug environment setup:

```bash
# Check environment variables
python scripts/debug_environment.py

# Verify Gmail auth
python -c "from src.email.gmail_client import GmailClient; GmailClient().authenticate()"
```

## Security Notes

### Never Commit

- `.env` - Contains secrets
- `credentials.json` - OAuth app credentials
- `token.pickle` - OAuth access token
- Any file with passwords or API keys

### .gitignore

Ensure these patterns are in `.gitignore`:

```
.env
credentials.json
token.pickle
*.pickle
```
