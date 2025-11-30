

import asyncio
import os
import sys
from loguru import logger
from playwright.async_api import async_playwright

# Add project root to path
sys.path.append(os.getcwd())

async def main():
    logger.info("Setting up browser profile for persistent authentication...")
    
    # Define profile path
    profile_path = os.path.join(os.getcwd(), "profiles", "default")
    os.makedirs(profile_path, exist_ok=True)
    
    logger.info(f"Profile directory: {profile_path}")
    logger.info("Launching browser... Please log in to Google/Office Hours manually.")
    logger.info("When finished, close the browser window to save the session.")
    
    async with async_playwright() as p:
        # Launch persistent context
        # We disable automation flags to make it easier to log in manually without detection
        # REMOVED channel="chrome" to ensure compatibility with agent's bundled Chromium
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            viewport={"width": 1280, "height": 800}
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Navigate to Office Hours login
        await page.goto("https://officehours.com/login")
        
        print("\n" + "="*60)
        print("BROWSER READY FOR MANUAL LOGIN")
        print("="*60)
        print("1. Log in to Office Hours using 'Continue with Google'")
        print("2. Complete any 2FA or security challenges")
        print("3. Verify you are on the dashboard")
        print("4. Close the browser window when done")
        print("="*60 + "\n")
        
        # Keep script running until browser is closed
        try:
            await page.wait_for_event("close", timeout=0)
        except:
            pass
            
        logger.info("Browser closed. Verifying captured cookies...")
        
        # We need to re-open briefly to read cookies from the profile
        # (Since we can't read them after context closes, and we can't read them while user is using it easily without interrupting)
        # Actually, we can check the Cookies file size
        
    # Check cookie file size
    cookie_file = os.path.join(profile_path, "Default", "Cookies")
    if os.path.exists(cookie_file):
        size = os.path.getsize(cookie_file)
        logger.info(f"Cookie file size: {size} bytes")
        if size > 0:
            print("✅ Profile saved with data.")
        else:
            print("⚠️ Warning: Cookie file is empty.")
    else:
        print("❌ Error: Cookie file not found.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
