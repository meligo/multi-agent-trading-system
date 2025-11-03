#!/usr/bin/env python3
"""
Test IG credentials with password variations
Sometimes $ needs to be escaped or the password format is different
"""

from trading_ig import IGService

def test_credentials(api_key, username, password, desc):
    """Test IG credentials."""
    print(f"\n{'='*80}")
    print(f" Testing: {desc}")
    print(f"{'='*80}")
    print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
    print(f"Username: {username}")
    print(f"Password: {password}")

    try:
        ig_service = IGService(
            username=username,
            password=password,
            api_key=api_key,
            acc_type='DEMO'
        )

        ig_service.create_session()
        accounts = ig_service.fetch_accounts()

        print(f"\n✅ SUCCESS!")
        print(f"Accounts: {len(accounts)}")
        for acc in accounts:
            print(f"  - {acc['accountName']}: {acc['balance']['balance']}")

        ig_service.logout()
        return True

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False


def main():
    api_key = "79ae278ca555968dda0d4837b90b813c4c941fdc"
    username = "meligokes"

    # Try different password variations
    passwords = [
        ("$Demo001", "Original from .env.scalper"),
        ("\\$Demo001", "Escaped dollar sign"),
        ("Demo001", "Without dollar sign"),
        ("$demo001", "Lowercase d"),
        ("DEMO001", "Uppercase only"),
    ]

    print("\n" + "="*80)
    print(" IG CREDENTIAL PASSWORD TESTING")
    print(" Trying different password formats")
    print("="*80)

    for password, desc in passwords:
        if test_credentials(api_key, username, password, desc):
            print(f"\n\n🎉 FOUND WORKING PASSWORD FORMAT: {desc}")
            print(f"   Password: {password}")
            break
    else:
        print(f"\n\n❌ NONE of the password formats worked")
        print(f"\n   Possible issues:")
        print(f"   1. Password is completely wrong")
        print(f"   2. Account is locked/suspended")
        print(f"   3. Need to reset password on IG website")
        print(f"   4. Need to verify email/account first")
        print(f"\n   Go to: https://www.ig.com/ and try logging in manually")


if __name__ == "__main__":
    main()
