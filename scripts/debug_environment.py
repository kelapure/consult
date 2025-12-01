#!/usr/bin/env python3
"""Debug script to test environment variable loading and credential access."""

import os
import sys
from dotenv import load_dotenv


def debug_environment():
    """Test environment loading for all platforms."""

    print("=== Environment Debug Report ===\n")

    # Test basic load_dotenv()
    print("1. Loading .env file...")
    load_dotenv()
    print("✓ load_dotenv() completed\n")

    # Test core credentials
    print("2. Core credentials:")
    core_vars = ['ANTHROPIC_API_KEY', 'GMAIL_EMAIL', 'GOOGLE_API_KEY']
    for var in core_vars:
        value = os.getenv(var)
        status = "✓" if value else "✗"
        print(f"  {var}: {status}")
    print()

    # Test platform credentials
    platforms = ['glg', 'guidepoint', 'coleman', 'office_hours']

    for platform in platforms:
        print(f"3. {platform.upper()} platform credentials:")
        prefix = platform.upper()

        vars_to_check = [
            f"{prefix}_USERNAME",
            f"{prefix}_PASSWORD",
            f"{prefix}_LOGIN_URL",
            f"{prefix}_DASHBOARD_URL"
        ]

        for var in vars_to_check:
            value = os.getenv(var)
            status = "✓" if value else "✗"
            display_value = ""
            if value and "PASSWORD" not in var:
                if len(value) > 10:
                    display_value = f" ({value[:3]}...{value[-3:]})"
                else:
                    display_value = f" ({value})"
            elif value and "PASSWORD" in var:
                display_value = " (***)"

            print(f"  {var}: {status}{display_value}")
        print()

    # Test subprocess environment inheritance
    print("4. Subprocess environment test:")
    missing_in_subprocess = []
    for platform in platforms:
        prefix = platform.upper()
        username_var = f"{prefix}_USERNAME"
        password_var = f"{prefix}_PASSWORD"

        # Check if variables are in os.environ (available to subprocesses)
        username_in_env = username_var in os.environ
        password_in_env = password_var in os.environ

        if os.getenv(username_var) and not username_in_env:
            missing_in_subprocess.append(username_var)
        if os.getenv(password_var) and not password_in_env:
            missing_in_subprocess.append(password_var)

    if missing_in_subprocess:
        print("  ✗ Variables available via getenv() but NOT exported to subprocess:")
        for var in missing_in_subprocess:
            print(f"    - {var}")
        print("  This will cause authentication failures in Claude Agent SDK context!")
    else:
        print("  ✓ All credentials properly exported to subprocess environment")

    print()

    # Test Claude Agent SDK specific variables
    print("5. Claude Agent SDK context:")
    sdk_vars = ['ANTHROPIC_API_KEY']
    for var in sdk_vars:
        getenv_value = os.getenv(var)
        environ_value = os.environ.get(var)

        print(f"  {var}:")
        print(f"    os.getenv(): {'✓' if getenv_value else '✗'}")
        print(f"    os.environ: {'✓' if environ_value else '✗'}")
        if getenv_value != environ_value:
            print(f"    ⚠️  MISMATCH: getenv() and environ have different values!")
    print()

    # Final assessment
    print("=== ASSESSMENT ===")

    # Count missing core credentials
    missing_core = [var for var in core_vars if not os.getenv(var)]
    if missing_core:
        print(f"❌ CRITICAL: Missing core credentials: {missing_core}")
        print("   System will not function without these!")
    else:
        print("✅ Core credentials: All present")

    # Count available platforms
    available_platforms = []
    for platform in platforms:
        prefix = platform.upper()
        username = os.getenv(f"{prefix}_USERNAME")
        password = os.getenv(f"{prefix}_PASSWORD")

        if platform == 'office_hours':
            # Google OAuth platform only needs dashboard URL
            dashboard_url = os.getenv(f"{prefix}_DASHBOARD_URL")
            if dashboard_url:
                available_platforms.append(f"{platform} (Google OAuth)")
        else:
            # Credential-based platforms need username and password
            if username and password:
                available_platforms.append(f"{platform} (credentials)")

    if available_platforms:
        print(f"✅ Available platforms: {', '.join(available_platforms)}")
    else:
        print("❌ No platforms have complete credentials!")

    if missing_in_subprocess:
        print("⚠️  WARNING: Some variables not exported to subprocess - will cause Agent SDK failures")
    else:
        print("✅ Subprocess inheritance: All variables properly exported")

    print("\n=== RECOMMENDATIONS ===")
    if missing_core:
        print("1. Add missing core credentials to .env file")
    if missing_in_subprocess:
        print("2. Ensure main.py calls validate_and_export_credentials() to export variables")
    if not available_platforms:
        print("3. Add platform credentials to .env file using the format:")
        print("   PLATFORM_USERNAME=your-username")
        print("   PLATFORM_PASSWORD=your-password")
        print("   PLATFORM_LOGIN_URL=https://platform.com/login")
        print("   PLATFORM_DASHBOARD_URL=https://platform.com/dashboard")

    if missing_core or missing_in_subprocess or not available_platforms:
        return 1  # Exit with error
    else:
        print("✅ Environment is properly configured!")
        return 0


if __name__ == "__main__":
    exit_code = debug_environment()
    sys.exit(exit_code)