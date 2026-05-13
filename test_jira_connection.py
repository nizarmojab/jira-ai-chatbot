#!/usr/bin/env python3
"""
test_jira_connection.py
=======================
Test Jira Cloud API connection with current credentials.
"""
import sys
import requests
from requests.auth import HTTPBasicAuth
from config import config


def test_jira_connection():
    """
    Test Jira API connection by calling GET /rest/api/3/myself.

    Returns:
        tuple: (success: bool, message: str, user_data: dict or None)
    """
    # Validate configuration first
    is_valid, messages = config.validate_all()

    print("="*70)
    print("[CONFIG] JIRA MULTI-AGENT CHATBOT - CONNECTION TEST")
    print("="*70)
    print()

    # Print validation results
    for msg in messages:
        print(msg)

    if not is_valid:
        print()
        print("[WARNING]  Configuration validation failed!")
        print("Please check your .env file and ensure all required variables are set.")
        return False, "Configuration validation failed", None

    print()
    print("[TEST] Testing Jira API connection...")
    print(f"   URL: {config.JIRA_BASE_URL}")
    print(f"   User: {config.JIRA_EMAIL}")
    print()

    # Test API connection
    try:
        url = f"{config.JIRA_BASE_URL}/rest/api/3/myself"
        auth = HTTPBasicAuth(config.JIRA_EMAIL, config.JIRA_API_TOKEN)

        response = requests.get(
            url,
            auth=auth,
            headers={"Accept": "application/json"},
            timeout=10
        )

        response.raise_for_status()
        user_data = response.json()

        # Success!
        print("[SUCCESS] CONNECTION SUCCESSFUL!")
        print()
        print("[INFO] Authenticated User Information:")
        print(f"   • Display Name: {user_data.get('displayName', 'N/A')}")
        print(f"   • Email: {user_data.get('emailAddress', 'N/A')}")
        print(f"   • Account ID: {user_data.get('accountId', 'N/A')}")
        print(f"   • Account Type: {user_data.get('accountType', 'N/A')}")
        print(f"   • Active: {user_data.get('active', False)}")
        print()
        print("="*70)
        print("OK Ready to use Jira API!")
        print("="*70)

        return True, "Connection successful", user_data

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code

        print("[FAILED] CONNECTION FAILED!")
        print()

        if status_code == 401:
            print("[AUTH] Authentication Error (401 Unauthorized)")
            print("   Possible causes:")
            print("   • Invalid JIRA_API_TOKEN")
            print("   • Token has expired")
            print("   • Wrong JIRA_EMAIL")
            print()
            print("[TIP] To fix:")
            print("   1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens")
            print("   2. Create a new API token")
            print("   3. Update JIRA_API_TOKEN in your .env file")

        elif status_code == 403:
            print("[FORBIDDEN] Permission Error (403 Forbidden)")
            print("   Your account doesn't have permission to access this Jira instance.")

        elif status_code == 404:
            print("[NOT FOUND] Not Found (404)")
            print("   Check your JIRA_BASE_URL - it may be incorrect.")
            print(f"   Current: {config.JIRA_BASE_URL}")

        else:
            print(f"[WARNING]  HTTP Error {status_code}")
            print(f"   Response: {e.response.text[:200]}")

        print()
        print("="*70)
        return False, f"HTTP {status_code} error", None

    except requests.exceptions.ConnectionError:
        print("[FAILED] CONNECTION FAILED!")
        print()
        print("[NETWORK] Network Error")
        print("   Cannot reach Jira server.")
        print("   • Check your internet connection")
        print("   • Verify JIRA_BASE_URL is correct")
        print(f"   • Current URL: {config.JIRA_BASE_URL}")
        print()
        print("="*70)
        return False, "Network connection error", None

    except requests.exceptions.Timeout:
        print("[FAILED] CONNECTION FAILED!")
        print()
        print("[TIMEOUT]  Timeout Error")
        print("   Request took too long (>10 seconds)")
        print("   • Check your internet connection")
        print("   • Jira server may be slow or down")
        print()
        print("="*70)
        return False, "Request timeout", None

    except Exception as e:
        print("[FAILED] UNEXPECTED ERROR!")
        print()
        print(f"[WARNING]  {type(e).__name__}: {str(e)}")
        print()
        print("="*70)
        return False, f"Unexpected error: {str(e)}", None


def main():
    """Main entry point."""
    success, message, user_data = test_jira_connection()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
