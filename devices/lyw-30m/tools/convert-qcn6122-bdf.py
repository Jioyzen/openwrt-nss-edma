#!/usr/bin/env python3
"""Convert this board's OEM QCN6122 BDF for the HK2.7 firmware in RAM images.

Reference: https://memo205.hatenablog.jp/entry/2025/02/15/074907
Only change the known schema byte and its XOR checksum. Never alter ART.
"""
import argparse
from functools import reduce
import hashlib
from pathlib import Path
import struct

cli = argparse.ArgumentParser()
cli.add_argument('source', type=Path)
cli.add_argument('output', type=Path)
args = cli.parse_args()
original = args.source.read_bytes()
assert len(original) == 0x20000
assert hashlib.sha256(original).hexdigest() == 'f65f26a7ad212898c2ccd2fdfcc89de7b8b72b1e957b5e1532988a18a543a38d'
assert reduce(int.__xor__, struct.unpack('<65536H', original)) == 0xffff
assert original[0x45c] == 3
converted = bytearray(original)
converted[0x45c] = 0
struct.pack_into('<H', converted, 0xa, 0)
checksum = reduce(int.__xor__, struct.unpack('<65536H', converted)) ^ 0xffff
struct.pack_into('<H', converted, 0xa, checksum)
assert reduce(int.__xor__, struct.unpack('<65536H', converted)) == 0xffff
changes = [i for i, (a, b) in enumerate(zip(original, converted)) if a != b]
assert set(changes) <= {0xa, 0xb, 0x45c}
args.output.write_bytes(converted)
print('Changes:', [hex(x) for x in changes])
print('SHA256:', hashlib.sha256(converted).hexdigest())
