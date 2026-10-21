#!/usr/bin/env python3
"""Check an extracted LYW-30M rootfs before accepting a candidate image.

This checks image contents, not just Kconfig selections or build exit status.
It does not establish hardware or throughput compatibility.
"""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Root extracted from the candidate squashfs/cpio")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    device = Path(__file__).resolve().parent
    lock = json.loads((device / "source-lock.json").read_text())
    packages = {line.split(" - ", 1)[0] for line in args.manifest.read_text().splitlines()}
    required = {
        "ath11k-firmware-ipq5018-qcn6122", "kmod-ath11k", "kmod-ath11k-ahb",
        "hostapd-basic-mbedtls", "dnsmasq", "firewall4", "ppp-mod-pppoe",
        "odhcp6c", "odhcpd-ipv6only", "kmod-qca-nss-drv", "kmod-qca-nss-ecm",
        "kmod-qca-dwmac-nss", "kmod-qca-dsa-nss", "kmod-qca8337-nss",
        "kmod-qca-nss-drv-pppoe", "kmod-qca-nss-drv-vlan-mgr",
        "nss-firmware-ipq50xx", "nss-tools-dwmac", "luci-base", "luci-mod-network",
        "luci-mod-status", "luci-mod-system", "luci-app-firewall",
        "luci-app-package-manager", "luci-i18n-base-zh-cn", "luci-theme-argon",
        "luci-app-nss", "luci-i18n-nss-zh-cn",
        "kmod-thermal", "uhttpd", "uhttpd-mod-ubus", "dropbear",
    }
    errors = [f"Missing package: {name}" for name in sorted(required - packages)]

    def read(name):
        path = args.root / name
        # Resolve absolute target symlinks inside this root, never on the host.
        if path.is_symlink() and path.readlink().is_absolute():
            path = args.root / str(path.readlink()).lstrip("/")
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"Missing/empty rootfs file: {name}")
            return b""
        return path.read_bytes()

    for name in (
        "bin/busybox", "usr/sbin/hostapd", "usr/sbin/dnsmasq", "sbin/fw4",
        "usr/sbin/pppd", "usr/sbin/odhcp6c", "usr/sbin/uhttpd",
        "usr/sbin/dropbear", "usr/sbin/nss-status", "usr/sbin/nss-dwmac-up",
        "etc/init.d/nss", "etc/init.d/qca-nss-pbuf", "etc/config/nss",
        "etc/lyw-release", "etc/uci-defaults/99-lyw-nss-mode",
        "usr/share/luci/menu.d/luci-app-firewall.json",
        "usr/share/luci/menu.d/luci-app-package-manager.json",
        "usr/share/luci/menu.d/luci-app-nss.json",
        "usr/share/rpcd/acl.d/luci-app-nss.json",
        "www/luci-static/resources/view/nss/status.js",
        "usr/lib/lua/luci/i18n/nss.zh-cn.lmo",
        "lib/firmware/qca-nss0-retail.bin",
    ):
        read(name)
    # QCN6122 shares the IPQ5018 Q6 image; its own directory holds M3.
    read("lib/firmware/ath11k/IPQ5018/hw1.0/q6_fw.mdt")
    read("lib/firmware/ath11k/QCN6122/hw1.0/m3_fw.mdt")
    for name, digest in lock["private_bdf_sha256"].items():
        if hashlib.sha256(read(name)).hexdigest() != digest:
            errors.append(f"BDF differs from validated board data: {name}")
    for name in ("ath11k", "ath11k_ahb", "qca-nss-drv", "ecm",
                 "qca-dwmac-nss", "qca-dsa-nss", "qca8337-nss"):
        data = read(f"lib/modules/{lock['kernel']}/{name}.ko")
        if data and f"vermagic={lock['kernel']} ".encode() not in data:
            errors.append(f"Unexpected module kernel version: {name}")
    release = read("etc/lyw-release").decode()
    for item in ("DEVICE=LYW-30M", f"KERNEL={lock['kernel']}"):
        if item not in release.splitlines():
            errors.append(f"Missing release identity: {item}")
    result = {"packages": len(packages), "required_packages": len(required),
              "board_bdf_matches": not any("BDF" in e for e in errors),
              "errors": errors, "passed": not errors}
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
