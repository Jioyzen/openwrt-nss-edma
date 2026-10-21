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
    # Older lock entries name driver patches by basename. Explicit paths
    # also allow backports for qca-nss-clients without mis-staging them in
    # the driver source package.
    relative = pathlib.Path(name)
    if len(relative.parts) == 1:
        relative = pathlib.Path('qca-nss-drv/patches') / relative
    if (len(relative.parts) != 3 or
            relative.parts[0] not in ('qca-nss-drv', 'qca-nss-clients') or
            relative.parts[1] != 'patches' or relative.suffix != '.patch'):
        raise SystemExit(f'Invalid NSS patch destination: {name}')
    dst = pathlib.Path('feeds/nss') / relative
    if dst.exists() and dst.read_bytes() != data:
        raise SystemExit(f'Conflicting patch: {dst}')
    pending.append((dst, data))
for dst, data in pending:
    dst.write_bytes(data)
print(f'Pinned feeds verified; {len(pending)} LYW-30M NSS patches staged.')
PY
./scripts/feeds install -a
