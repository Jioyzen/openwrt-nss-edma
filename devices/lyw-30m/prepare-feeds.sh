#!/bin/sh
# Run in a dedicated clone/worktree; preserve a developer's src-link feeds.
set -eu
cd "$(dirname "$0")/../.."
if [ -e feeds.conf ] && ! cmp -s feeds.conf devices/lyw-30m/feeds.lock.conf; then
	echo 'Existing feeds.conf differs; use a fresh clone/worktree.' >&2
	exit 1
fi
cp devices/lyw-30m/feeds.lock.conf feeds.conf
./scripts/feeds update -a
python3 - <<'PY'
import hashlib
import json
import pathlib
import subprocess

device = pathlib.Path('devices/lyw-30m')
lock = json.loads((device / 'source-lock.json').read_text())
for name, feed in lock['feeds'].items():
    path = pathlib.Path('feeds') / name
    sha = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    if sha != feed['commit']:
        raise SystemExit(f'{name}: unexpected commit {sha}')
    if subprocess.check_output(['git', '-C', str(path), 'diff', 'HEAD', '--'], text=True):
        raise SystemExit(f'{name}: tracked local changes; refusing to continue')
pending = []
for name, digest in lock['nss_patches'].items():
    src = device / 'feeds/nss' / name
    data = src.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise SystemExit(f'Patch checksum mismatch: {name}')
    dst = pathlib.Path('feeds/nss/qca-nss-drv/patches') / name
    if dst.exists() and dst.read_bytes() != data:
        raise SystemExit(f'Conflicting patch: {dst}')
    pending.append((dst, data))
for dst, data in pending:
    dst.write_bytes(data)
print('Pinned feeds verified; two LYW-30M NSS patches staged.')
PY
./scripts/feeds install -a
