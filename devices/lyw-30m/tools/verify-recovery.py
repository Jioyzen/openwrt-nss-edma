#!/usr/bin/env python3
"""Validate the dedicated RAM recovery FIT, including its writable region policy."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preflight_fit import parse_dtb, string, integer

p = argparse.ArgumentParser()
p.add_argument('image', type=Path)
p.add_argument('report', type=Path)
p.add_argument('--single', action='store_true')
a = p.parse_args()
blob = a.image.read_bytes()
fit = parse_dtb(blob)
assert string(fit['/configurations']['default']) == 'config@mp03.3'
c = fit['/configurations/config@mp03.3']
k = '/images/' + string(c['kernel'])
d = '/images/' + string(c['fdt'])
assert string(fit[k]['arch']) == 'arm64'
assert integer(fit[k]['load']) == integer(fit[k]['entry']) == 0x41000000
kernel = lzma.decompress(fit[k]['data'], format=lzma.FORMAT_ALONE)
assert kernel[56:60] == b'ARM\x64'
assert 0x41000000 + len(kernel) < 0x44000000
hashes = 0
for n, props in fit.items():
    if n.startswith((k+'/hash', d+'/hash')):
        data = fit[n.rsplit('/', 1)[0]]['data']
        algorithm = string(props['algo'])
        digest = struct.pack('>I', zlib.crc32(data)) if algorithm == 'crc32' else hashlib.new(algorithm, data).digest()
        assert digest == props['value']
        hashes += 1
assert hashes >= 4
tree = parse_dtb(fit[d]['data'])
assert b'lingyan,lyw-30m\0' in tree['/']['compatible']
parts = {string(props['label']): (list(struct.unpack('>II', props['reg'])), 'read-only' in props)
         for n, props in tree.items()
         if '/partitions/partition@' in n and '/' not in n.split('/partition@')[1]}
if a.single:
    assert len(parts) == 16
    assert parts['rootfs'] == ([0x900000, 0x7700000], False)
    assert {n for n, item in parts.items() if not item[1]} == {'rootfs'}
    assert not {'stock_rootfs', 'rootfs_1', 'plugins'} & parts.keys()
    end = 0
    for (offset, length), ro in sorted(parts.values()):
        assert offset == end
        end = offset + length
    assert end == 0x8000000
else:
    assert len(parts) == 18
    assert parts['stock_rootfs'] == ([0x900000, 0x2840000], True)
    assert parts['rootfs'] == ([0x3140000, 0x2840000], False)
    assert {n for n, item in parts.items() if not item[1]} == {'0:BOOTCONFIG', '0:BOOTCONFIG1', 'rootfs'}
assert tree['/reserved-memory/tz@4ac00000']['reg'] == struct.pack('>IIII', 0, 0x4ac00000, 0, 0x400000)
assert b'ubi.mtd=' not in tree['/chosen']['bootargs-append']
result = {'image': str(a.image), 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest(),
          'crc32': format(zlib.crc32(blob), '08x'), 'kernel_expanded_bytes': len(kernel),
          'FIT_hashes_verified': hashes, 'partition_policy_verified': True,
          'storage_layout': 'single-ubi-v1' if a.single else 'legacy-slot1',
          'boot_method': 'RAM initramfs; pass no ubi.mtd argument'}
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
