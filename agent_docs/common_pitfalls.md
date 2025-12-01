# Common Pitfalls & Troubleshooting

Solutions for common issues when working with the Consultation Automation Agent.

## Gmail Authentication

### Issue: OAuth Flow Required

**Symptom**: First run opens browser, asks for Google account permission

**Solution**: This is expected behavior. Complete the OAuth flow once.

```bash
# After first run, token.pickle is created
ls token.pickle  # Should exist after successful auth
```

### Issue: Token Expired

**Symptom**: "Invalid credentials" or "Token expired" errors

**Solution**: Delete token and re-authenticate:

```bash
rm token.pickle
python main.py --platform glg
# Complete OAuth flow in browser
```

### Issue: Credentials Not Found

**Symptom**: "credentials.json not found"

**Solution**:

1. Go to Google Cloud Console
2. Create/select project
3. Enable Gmail API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download as `credentials.json` to project root

## Browser Automation

### Issue: Coordinate Mismatch (Gemini)

**Symptom**: Clicks miss targets, forms not filled correctly

**Cause**: Gemini uses 0-1000 normalized coordinates

**Solution**: Verify viewport resolution matches expected values. Check `src/browser/computer_use.py` for conversion logic.

### Issue: Headless Mode Failures

**Symptom**: Works with `--debug` but fails in headless mode

**Solution**:

1. Check for popups that only appear in headless
2. Increase timeouts
3. Add debug screenshots: `python main.py --debug`

### Issue: Element Not Found

**Symptom**: "Element not found" or timeout waiting for element

**Possible Causes**:

- Platform UI changed
- Different page structure for logged-in users
- Cookie consent blocking

**Solution**:

```bash
# Test with debug mode
python main.py --platform glg --debug

# Check screenshots in screenshots/ folder
ls screenshots/
```

## Platform Credentials

### Issue: Missing Credentials

**Symptom**: "Missing login credentials for platform: xxx"

**Solution**:

1. Check `.env` file has correct variables
2. Use exact naming pattern: `{PLATFORM}_USERNAME`, `{PLATFORM}_PASSWORD`
3. Restart after changing `.env`

```bash
# Debug environment
python scripts/debug_environment.py
```

### Issue: Login Failed

**Symptom**: Browser automation can't log in

**Possible Causes**:

- Wrong credentials
- 2FA enabled
- Account locked
- CAPTCHA required

**Solution**:

1. Verify credentials work manually
2. Disable 2FA for automation account (if possible)
3. Use a dedicated automation account

## Agent Issues

### Issue: Agent Not Making Decisions

**Symptom**: Agent loops without taking action

**Cause**: System prompt unclear or tools not returning expected data

**Solution**: Check logs for tool call results:

```bash
tail -f logs/consultation_*.log | grep -i "tool\|decision"
```

### Issue: Wrong Decisions

**Symptom**: Agent accepts/declines incorrectly

**Solution**: Modify system prompt in `src/agent/consult_agent.py`:

```python
SYSTEM_PROMPT = """
# Decision criteria defined here
...
"""
```

## Memory & Persistence

### Issue: Duplicate Processing

**Symptom**: Same emails processed multiple times

**Solution**: Check memory store:

```bash
# View processed emails
cat logs/memory_store.json | python -m json.tool
```

### Issue: Memory Store Corrupted

**Symptom**: JSON parse errors

**Solution**:

```bash
# Backup and reset
mv logs/memory_store.json logs/memory_store.json.bak
# Next run will create fresh store
```

## Debug Commands

### Check Environment

```bash
python scripts/debug_environment.py
```

### Follow Logs

```bash
tail -f logs/consultation_*.log
```

### Test Gmail Connection

```bash
python -c "from src.email.gmail_client import GmailClient; GmailClient().authenticate(); print('OK')"
```

### Test Profile Loading

```bash
python -c "from src.profile.aggregator import ProfileAggregator; import asyncio; print(asyncio.run(ProfileAggregator().aggregate()))"
```

### View Recent Metrics

```bash
python main.py --view-metrics 7
```

### View Run History

```bash
python main.py --view-runs 10
```

## Performance Issues

### Issue: Slow Processing

**Possible Causes**:

- Too many emails to process
- Slow API responses
- Network latency

**Solutions**:

```bash
# Limit days to look back
python main.py --days 3

# Focus on single platform
python main.py --platform glg
```

### Issue: High API Costs

**Solution**: Monitor usage and adjust:

- Use `--days` to limit email scope
- Use platform filter to focus runs
- Consider rate limiting
