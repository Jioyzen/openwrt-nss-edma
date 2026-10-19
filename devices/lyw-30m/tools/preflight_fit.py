#!/usr/bin/env python3
"""Inspect the built RAM artifact before allowing a manual U-Boot test."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import struct
import zlib


def parse_dtb(data):
    header = struct.unpack_from(">10I", data)
    if header[0] != 0xd00dfeed or header[1] > len(data):
        raise ValueError("Invalid/truncated DTB")
    cursor, strings = header[2], header[3]
    nodes, stack = {}, []
    while cursor < header[2] + header[9]:
        token, = struct.unpack_from(">I", data, cursor)
        cursor += 4
        if token == 1:
            end = data.index(b"\0", cursor)
            stack.append(data[cursor:end].decode())
            cursor = (end + 4) & ~3
            nodes["/".join(stack) or "/"] = {}
        elif token == 2:
            stack.pop()
        elif token == 3:
            length, name_offset = struct.unpack_from(">II", data, cursor)
            cursor += 8
            end = data.index(b"\0", strings + name_offset)
            name = data[strings + name_offset:end].decode()
            nodes["/".join(stack) or "/"][name] = data[cursor:cursor + length]
            cursor = (cursor + length + 3) & ~3
        elif token == 9:
            break
        elif token != 4:
            raise ValueError(f"Unknown DTB token {token}")
    return nodes


def string(data):
    return data.rstrip(b"\0").decode()


def integer(data):
    return int.from_bytes(data, "big")


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("image", type=Path)
    cli.add_argument("--allow-arm-fit-wrapper", action="store_true")
    cli.add_argument("--wifi", action="store_true", help="Validate the staged Wi-Fi RAM image")
    args = cli.parse_args()
    blob = args.image.read_bytes()
    nodes = parse_dtb(blob)
    config_name = "config@mp03.3"
    assert string(nodes["/configurations"]["default"]) == config_name
    config = nodes[f"/configurations/{config_name}"]
    kernel_path = "/images/" + string(config["kernel"])
    fdt_path = "/images/" + string(config["fdt"])
    kernel = nodes[kernel_path]
    architecture = string(kernel["arch"])
    assert architecture == "arm64" or (args.allow_arm_fit_wrapper and architecture == "arm")
    assert string(kernel["compression"]) == "lzma"
    payload = lzma.decompress(kernel["data"], format=lzma.FORMAT_ALONE)
    assert payload[56:60] == b"ARM\x64", "Payload is not an AArch64 Linux Image"
    image_size, = struct.unpack_from("<Q", payload, 16)
    load, entry = integer(kernel["load"]), integer(kernel["entry"])
    assert load == entry == 0x41000000
    memory_end = load + max(image_size, len(payload))
    assert memory_end <= 0x44000000, "Decompression overlaps the FIT staging address"
    assert 0x44000000 + len(blob) < 0x4a400000
    assert b"LYW RAM test: master NAND forced read-only" in payload
    verified_hashes = []
    for image_path in (kernel_path, fdt_path):
        for path, properties in nodes.items():
            if not path.startswith(image_path + "/hash"):
                continue
            algorithm = string(properties["algo"])
            data = nodes[image_path]["data"]
            if algorithm == "crc32":
                digest = struct.pack(">I", zlib.crc32(data))
            else:
                digest = hashlib.new(algorithm, data).digest()
            assert digest == properties["value"], f"Bad {algorithm} for {image_path}"
            verified_hashes.append(f"{image_path}:{algorithm}")
    assert len(verified_hashes) >= 4
    tree = parse_dtb(nodes[fdt_path]["data"])
    assert b"lingyan,lyw-30m\0" in tree["/"]["compatible"]
    partitions = {}
    for path, properties in tree.items():
        if "/partitions/partition@" not in path or "/" in path.split("/partition@", 1)[1]:
            continue
        assert "read-only" in properties
        partitions[string(properties["label"])] = struct.unpack(">II", properties["reg"])
    expected = {
        "0:SBL1": (0, 0x80000), "0:MIBIB": (0x80000, 0x80000),
        "0:BOOTCONFIG": (0x100000, 0x40000), "0:BOOTCONFIG1": (0x140000, 0x40000),
        "0:ART": (0x780000, 0x100000), "rootfs": (0x900000, 0x2840000),
        "rootfs_1": (0x3140000, 0x2840000), "plugins": (0x5980000, 0x23c0000),
    }
    assert len(partitions) == 18
    assert all(partitions[name] == bounds for name, bounds in expected.items())
    memory = [p for p in tree.values() if p.get("device_type") == b"memory\0"]
    assert len(memory) == 1
    assert memory[0]["reg"] == struct.pack(">IIII", 0, 0x40000000, 0, 0x10000000)
    assert tree["/reserved-memory/tz@4ac00000"]["reg"] == struct.pack(">IIII", 0, 0x4ac00000, 0, 0x400000)
    assert tree["/reserved-memory/nss@40000000"]["reg"] == struct.pack(">IIII", 0, 0x40000000, 0, 0x1000000)
    chosen = tree["/chosen"]
    assert b"ubi.mtd=" not in chosen.get("bootargs-append", b"")
    wireless = [p for p in tree.values() if any(c in p.get("compatible", b"")
                for c in (b"qcom,ipq5018-wifi", b"qcom,qcn6122-wifi"))]
    assert len(wireless) >= 2
    if args.wifi:
        enabled = [p for p in wireless if p.get("status") == b"okay\0"]
        assert len(enabled) == 2
        assert sorted(integer(p["reg"][:4]) for p in enabled) == [0xb00a040, 0xc000000]
        for p in enabled:
            assert p["qcom,ath11k-calibration-variant"] == b"LINGYAN-LYW-30M\0"
            assert integer(p["qcom,ath11k-fw-memory-mode"]) == 1
        wcss = [p for p in tree.values() if b"qcom,ipq5018-q6-mpd\0" in p.get("compatible", b"")]
        assert len(wcss) == 1
        assert wcss[0]["boot-args"] == struct.pack(">6I", 2, 4, 2, 18, 0, 0)
    else:
        assert all(p.get("status") == b"disabled\0" for p in wireless)
    print(json.dumps({
        "file": str(args.image), "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
        "fit_configuration": config_name, "fit_architecture": architecture,
        "payload_architecture": "AArch64", "kernel_load": hex(load),
        "kernel_memory_end": hex(memory_end), "decompressed_bytes": len(payload),
        "verified_hashes": verified_hashes, "read_only_partitions": len(partitions),
        "nand_protection_marker": True, "wireless_disabled": not args.wifi,
    }, indent=2))


if __name__ == "__main__":
    main()
