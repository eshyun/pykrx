#!/usr/bin/env python
"""
Multi-process session sharing test.

This script demonstrates that session storage is shared across processes.
Run this script multiple times in different terminals to see session sharing in action.
"""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from pykrx.website.comm.webio import get_http_session, set_http_session
from pykrx.website.krx.krxio import (
    _get_session_file_path,
    _load_session_from_file,
    clear_session_file,
)


def main():
    print("=" * 60)
    print(f"Process PID: {os.getpid()}")
    print(f"Session file location: {_get_session_file_path()}")
    print("=" * 60)

    # Check memory session
    mem_session = get_http_session()
    if mem_session:
        print("✓ Session found in memory")
    else:
        print("✗ No session in memory")

    # Check file session
    session_file = _get_session_file_path()
    if session_file.exists():
        print(f"✓ Session file exists")

        # Try to load
        file_session = _load_session_from_file()
        if file_session:
            print("✓ Successfully loaded session from file")
            set_http_session(file_session)

            # Read session file to show info
            import json

            with open(session_file, "r") as f:
                data = json.load(f)
                print(f"  - Created: {data.get('created_at')}")
                print(f"  - Expires: {data.get('expires_at')}")
                print(f"  - Last used: {data.get('last_used')}")
                print(f"  - MBR_NO: {data.get('mbr_no')}")
                print(f"  - Cookies: {len(data.get('cookies', {}))} cookies")
        else:
            print("✗ Session file exists but is expired or invalid")
    else:
        print("✗ No session file found")
        print("\nTo test session sharing:")
        print("1. Run a pykrx function that requires login in another terminal")
        print("2. Then run this script again to see the shared session")

    print("=" * 60)


if __name__ == "__main__":
    main()
