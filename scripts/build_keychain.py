#!/usr/bin/env python3
"""Build the dedicated macOS Keychain helper in this Python environment."""
from pathlib import Path
import subprocess
import sys
import tempfile

if sys.platform != 'darwin':
    raise SystemExit('The native Keychain helper requires macOS')
source = Path(__file__).resolve().parent / 'native/keychain.swift'
output = Path(sys.prefix) / 'bin/f1-keychain'
with tempfile.TemporaryDirectory(prefix='f1-swift-cache-') as cache:
    subprocess.run(['/usr/bin/xcrun', 'swiftc', '-O', '-module-cache-path', cache,
                    str(source), '-o', str(output)], check=True)
output.chmod(0o700)
print('Built native Keychain helper:', output)
