#!/usr/bin/env python3
"""Stage local BDF files; source defaults are applied by the image build."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('private_root', type=Path,
                        help='Local directory containing lib/firmware/ath11k/.../board-2.bin')
    args = parser.parse_args()
    device = Path(__file__).resolve().parent
    root = device.parent.parent
    lock = json.loads((device / 'source-lock.json').read_text())
    pending = []
    for name, original_digest in lock['private_bdf_sha256'].items():
        src = args.private_root / name
        if not src.is_file() or src.stat().st_size == 0:
            raise SystemExit(f'Missing BDF: {src}')
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        print(f'{name}: sha256={digest}; matches NAND22={digest == original_digest}')
        pending.append((src, Path(name)))
    # Check every destination before copying. Never copy private_root
    # recursively: it may also contain host keys and unit settings.
    for src, relative in pending:
        dst = root / 'files' / relative
        if dst.exists() and dst.read_bytes() != src.read_bytes():
            raise SystemExit(f'Conflicting overlay file: {dst}; use a fresh worktree')
    for src, relative in pending:
        dst = root / 'files' / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    print(f'Staged {len(pending)} BDF files. Source defaults load during the build; ART/caldata remains on the router.')


if __name__ == '__main__':
    main()
