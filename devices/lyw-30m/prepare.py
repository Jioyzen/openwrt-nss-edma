#!/usr/bin/env python3
"""Stage a build using verified OEM board files supplied locally."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ipq5018-bdf', required=True, type=Path)
    parser.add_argument('--qcn6122-bdf', required=True, type=Path)
    parser.add_argument('--local-overlay', type=Path,
                        help='Optional private overrides; never commit these inputs')
    args = parser.parse_args()
    device = Path(__file__).resolve().parent
    root = device.parents[1]
    lock = json.loads((device / 'source-lock.json').read_text())
    encoder = device / 'tools/ath11k-bdencoder'
    if hashlib.sha256(encoder.read_bytes()).hexdigest() != lock['bdencoder_sha256']:
        parser.error('Board encoder checksum mismatch')
    inputs = {'IPQ5018': args.ipq5018_bdf.resolve(),
              'QCN6122': args.qcn6122_bdf.resolve()}
    for chip, path in inputs.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != lock['board_source_sha256'][chip]:
            parser.error(f'{chip}: input is not the verified OEM BDF for this board')
    if args.local_overlay and not args.local_overlay.is_dir():
        parser.error('--local-overlay must be a directory')
    # Refuse to overwrite a developer's active configuration or files overlay.
    for name in ['files', '.config', 'feeds.conf']:
        if (root / name).exists():
            parser.error(f'{root / name} already exists; use a clean checkout')
    with tempfile.TemporaryDirectory(prefix='lyw-boardfiles-') as temporary:
        temp = Path(temporary)
        stage = temp / 'files'
        shutil.copytree(device / 'overlay', stage)
        if args.local_overlay:
            shutil.copytree(args.local_overlay, stage, dirs_exist_ok=True)
        converted = temp / 'qcn6122-converted.bin'
        subprocess.run(['python3', str(device / 'tools/convert-qcn6122-bdf.py'),
                        str(inputs['QCN6122']), str(converted)], check=True)
        inputs['QCN6122'] = converted
        for chip, path in inputs.items():
            mapping = temp / f'{chip}.json'
            mapping.write_text(json.dumps([{'board': [{
                'names': ['bus=ahb,qmi-chip-id=0,qmi-board-id=255,variant=LINGYAN-LYW-30M'],
                'data': str(path),
            }]}]))
            target = stage / f'lib/firmware/ath11k/{chip}/hw1.0/board-2.bin'
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['python3', str(encoder), '-c', str(mapping),
                            '-o', str(target)], check=True)
            print(chip, hashlib.sha256(target.read_bytes()).hexdigest())
        shutil.copytree(stage, root / 'files')
    shutil.copy2(device / 'config.full', root / '.config')
    shutil.copy2(device / 'feeds.conf', root / 'feeds.conf')
    print('Staged config, pinned feeds and board files. Next:')
    print('./scripts/feeds update -a && ./scripts/feeds install -a')
    print('cp devices/lyw-30m/config.full .config')
    print('make defconfig && make -j$(nproc) V=s')


if __name__ == '__main__':
    main()
