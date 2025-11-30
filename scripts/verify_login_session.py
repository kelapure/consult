
import asyncio
import os
import sys
from playwright.async_api import async_playwright

# Add project root to path
sys.path.append(os.getcwd())

async def verify_session():
    profile_path = os.path.join(os.getcwd(), "profiles", "default")
    
    if not os.path.exists(profile_path):
        print(f"Error: Profile directory not found at {profile_path}")
        return

    print(f"Verifying session in profile: {profile_path}")
    
    async with async_playwright() as p:
        try:
            # Launch with the same persistent context
            context = await p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                headless=False, # Run headed for verification to match setup
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            page = context.pages[0] if context.pages else await context.new_page()
            
            target_url = "https://officehours.com/home"
            print(f"Navigating to {target_url}...")
            try:
                await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
                # Wait a bit for potential client-side redirects
                await asyncio.sleep(5)
            except Exception as nav_err:
                print(f"Navigation warning: {nav_err}")

            current_url = page.url
            title = await page.title()
            
            print(f"Current URL: {current_url}")
            print(f"Page Title: {title}")
            
            # Check for login indicators
            if "login" in current_url.lower() or "signin" in current_url.lower():
                print("❌ FAILED: Redirected to login page. Session is NOT valid.")
            elif "home" in current_url.lower() or "dashboard" in current_url.lower():
                print("✅ SUCCESS: stayed on home/dashboard URL.")
                
                # Check for specific logged-in elements if possible
                content = await page.content()
                if "Sign in" in content and "Profile" not in content:
                     print("⚠️ WARNING: Page loaded but might still show Sign In button.")
                else:
                     print("✅ Session appears valid.")
            else:
                print(f"❓ UNKNOWN: Landed on {current_url}. Please interpret manually.")

            await context.close()
            
        except Exception as e:
            print(f"Error during verification: {e}")

if __name__ == "__main__":
    asyncio.run(verify_session())
