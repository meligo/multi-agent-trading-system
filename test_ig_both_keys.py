#!/usr/bin/env python3
"""
Test BOTH IG API keys to see which one works
"""

import os
from dotenv import load_dotenv
from pathlib import Path

def test_ig_key(api_key, username, password, source_name):
    """Test a single IG API key."""
    print(f"\n{'='*80}")
    print(f" Testing IG Credentials from {source_name}")
    print(f"{'='*80}")
    print(f"\nAPI Key: {api_key[:20]}...{api_key[-10:]}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")

    try:
        from trading_ig import IGService

        ig_service = IGService(
            username=username,
            password=password,
            api_key=api_key,
            acc_type='DEMO'
        )

        # Try to create session
        ig_service.create_session()

        # Get accounts
        accounts = ig_service.fetch_accounts()

        print(f"\n✅ SUCCESS - This key WORKS!")
        print(f"   Accounts: {len(accounts)}")
        for acc in accounts:
            print(f"   - {acc['accountName']} ({acc['accountType']}): {acc['balance']['balance']}")

        ig_service.logout()
        return True

    except Exception as e:
        print(f"\n❌ FAILED - {e}")
        return False


def main():
    print("\n" + "="*80)
    print(" IG API KEY COMPARISON TEST")
    print(" Testing credentials from both .env files")
    print("="*80)

    # Test .env.scalper credentials
    env_scalper = Path(__file__).parent / '.env.scalper'
    load_dotenv(dotenv_path=env_scalper, override=True)

    scalper_key = os.getenv("IG_API_KEY")
    scalper_user = os.getenv("IG_USERNAME")
    scalper_pass = os.getenv("IG_PASSWORD")

    scalper_works = test_ig_key(scalper_key, scalper_user, scalper_pass, ".env.scalper")

    # Test .env credentials
    env_main = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_main, override=True)

    main_key = os.getenv("IG_API_KEY")
    main_user = os.getenv("IG_USERNAME")
    main_pass = os.getenv("IG_PASSWORD")

    main_works = test_ig_key(main_key, main_user, main_pass, ".env")

    # Summary
    print("\n" + "="*80)
    print(" SUMMARY")
    print("="*80)

    if scalper_works:
        print(f"\n✅ .env.scalper credentials WORK")
        print(f"   Use this file for scalping engine")
    elif main_works:
        print(f"\n✅ .env credentials WORK")
        print(f"   Should copy these to .env.scalper")
    else:
        print(f"\n❌ BOTH credential sets FAILED")
        print(f"\nYou need to:")
        print(f"   1. Log in to IG Markets")
        print(f"   2. Go to API settings")
        print(f"   3. Generate new API key")
        print(f"   4. Update .env.scalper with new credentials")
        print(f"\n   IG API Portal: https://labs.ig.com/")


if __name__ == "__main__":
    main()
