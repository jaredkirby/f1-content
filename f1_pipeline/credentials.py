"""OpenRouter credentials: explicit environment or this Mac's named Keychain item."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys


def valid_key(value):
    return isinstance(value, str) and 1 <= len(value) <= 512 and all(33 <= ord(c) <= 126 for c in value)


def native(action, value=None):
    helper = Path(sys.prefix) / 'bin' / 'f1-keychain'
    try:
        result = subprocess.run([str(helper), action], input=value, capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('Keychain helper unavailable; run scripts/build_keychain.py on this Mac') from None
    if result.returncode:
        # Native errors are deliberately not forwarded: never echo a credential.
        raise ValueError('Keychain unavailable, locked or access denied; no plaintext fallback')
    return result.stdout


def resolve_api_key():
    if 'OPENROUTER_API_KEY' in os.environ:
        return os.environ['OPENROUTER_API_KEY']
    if sys.platform != 'darwin' or os.environ.get('F1_DISABLE_KEYCHAIN') == '1':
        return ''
    try:
        value = native('read').decode('ascii')
    except (ValueError, UnicodeError):
        return ''
    return value if valid_key(value) else ''


def main(argv=None):
    parser = argparse.ArgumentParser(description='Manage the named OpenRouter Keychain item without printing its secret')
    parser.add_argument('action', choices=('store', 'status', 'delete'))
    args = parser.parse_args(argv)
    try:
        value = None
        if args.action == 'store':
            value = getpass.getpass('OpenRouter key (hidden): ') if sys.stdin.isatty() else sys.stdin.read(514).rstrip('\r\n')
            if not valid_key(value):
                raise ValueError('Invalid OpenRouter key format')
            value = value.encode('ascii')
        result = json.loads(native(args.action, value))
        if result.get('status') not in ('stored', 'available', 'missing', 'deleted'):
            raise ValueError('Invalid Keychain status')
        print(json.dumps({'status': result['status'], 'storage': 'macos_login_keychain'}))
        return 0
    except (ValueError, UnicodeError):
        print('Credential operation failed; Keychain may be locked, denied or unavailable. No plaintext fallback.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
