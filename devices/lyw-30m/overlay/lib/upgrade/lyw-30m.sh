#!/bin/sh
# Dedicated single-system UBI upgrades. The boot chain and calibration stay read-only.

lyw_layout_check() {
 [ "$(board_name)" = 'lingyan,lyw-30m' ] || return 1
 local index
 index=$(find_mtd_index rootfs)
 [ -n "$index" ] || return 1
 [ "$(cat /sys/class/mtd/mtd$index/offset)" = 9437184 ] || return 1
 [ "$(cat /sys/class/mtd/mtd$index/size)" = 124780544 ] || return 1
 [ "$(cat /sys/class/mtd/mtd$index/erasesize)" = 131072 ] || return 1
 [ "$(cat /sys/class/mtd/mtd$index/writesize)" = 2048 ] || return 1
 [ "$(cat /sys/class/mtd/mtd$index/oobsize)" = 64 ] || return 1
 [ "$(cat /sys/class/mtd/mtd$index/ecc_strength)" = 4 ] || return 1
 [ "$(cat /sys/class/mtd/mtd$index/ecc_step_size)" = 512 ] || return 1
 local rootflags=$(cat /sys/class/mtd/mtd$index/flags)
 [ "$((rootflags & 0x400))" -ne 0 ] || return 1
 [ "$(cat /etc/lyw-release | grep '^STORAGE_LAYOUT=')" = 'STORAGE_LAYOUT=single-ubi-v1' ] || return 1
 local other flags count=0
 for other in /sys/class/mtd/mtd[0-9]*; do
  case "$other" in *ro) continue ;; esac
  [ -f "$other/offset" ] || continue
  count=$((count+1))
  [ "$other" != "/sys/class/mtd/mtd$index" ] || continue
  flags=$(cat "$other/flags")
  [ "$((flags & 0x400))" = 0 ] || return 1
 done
 [ "$count" = 16 ] || return 1
}

lyw_check_image() {
 local file="$1"
 local dir='sysupgrade-lingyan_lyw-30m-single'
 lyw_layout_check || { echo 'LYW partition identity mismatch' >&2; return 1; }
 nand_do_platform_check lingyan,lyw-30m-single "$file" || return 1
 tar tf "$file" | grep -qx "$dir/kernel" || return 1
 tar tf "$file" | grep -qx "$dir/root" || return 1
 local kernel_length=$(tar xOf "$file" "$dir/kernel" | wc -c)
 local root_length=$(tar xOf "$file" "$dir/root" | wc -c)
 [ "$kernel_length" -gt 1000000 ] && [ "$root_length" -gt 1000000 ] || return 1
 local index=$(find_mtd_index rootfs)
 local bad=$(cat /sys/class/mtd/mtd$index/bad_blocks)
 # Reserve layout/WL blocks, conservative 20 bad blocks, and 17 UBIFS LEBs.
 local needed=$(( (kernel_length+126975)/126976 + (root_length+126975)/126976 + 41 ))
 [ "$needed" -le "$((952-bad))" ] || { echo 'Insufficient NAND capacity' >&2; return 1; }
 local kernel=/tmp/lyw-kernel-check.$$
 tar xOf "$file" "$dir/kernel" > "$kernel" || return 1
 local description=$(dumpimage -l "$kernel" 2>/dev/null)
 rm -f "$kernel"
 echo "$description" | grep -q 'AArch64' || return 1
 echo "$description" | grep -q 'config@mp03.3' || return 1
 echo "$description" | grep -q '41000000' || return 1
 local magic=$(tar xOf "$file" "$dir/root" | { dd bs=4 count=1 2>/dev/null; cat >/dev/null; } | hexdump -v -e '4/1 "%02x"')
 [ "$magic" = 68737173 ] || { echo 'Expected SquashFS root image' >&2; return 1; }
}

lyw_verify_written() {
 local file="$1"
 local dir='sysupgrade-lingyan_lyw-30m-single'
 local ubi=$(nand_find_ubi rootfs)
 [ -n "$ubi" ] || return 1
 local image volume length expected actual
 for image in kernel root; do
  volume=kernel
  [ "$image" != root ] || volume=rootfs
  volume=$(nand_find_volume "$ubi" "$volume")
  [ -n "$volume" ] || return 1
  length=$(tar xOf "$file" "$dir/$image" | wc -c)
  expected=$(tar xOf "$file" "$dir/$image" | sha256sum | cut -d' ' -f1)
  actual=$(head -c "$length" /dev/$volume | sha256sum | cut -d' ' -f1)
  [ "$expected" = "$actual" ] || { echo "LYW $image readback mismatch" >&2; return 1; }
 done
}

lyw_nand_upgrade() {
 local file="$1"
 CI_UBIPART=rootfs
 CI_KERNPART=kernel
 CI_ROOTPART=rootfs
 lyw_check_image "$file" || { nand_do_upgrade_failed; return 1; }
 mkdir -p /var/lock
 sync
 if nand_do_flash_file "$file" && lyw_verify_written "$file" && nand_do_restore_config && sync; then
  echo 'LYW single-system upgrade verified; boot environment and calibration retained.'
  umount -a
  reboot -f
 fi
 # The original U-Boot UART/TFTP RAM recovery remains available on failure.
 nand_do_upgrade_failed
}
