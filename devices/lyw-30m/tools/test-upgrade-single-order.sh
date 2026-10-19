#!/bin/bash
# Check failure ordering in the real single-system backend without NAND IO.
set -eu
helper=$1
for fault in none image flash verify restore; do
 trace=$(mktemp)
 set +e
 bash -s "$helper" "$fault" "$trace" <<'TEST'
source "$1"
fault=$2
trace=$3
record() { echo "$*" >> "$trace"; }
lyw_check_image() { record image; [ "$fault" != image ]; }
lyw-slot-control() { record UNEXPECTED_SLOT_WRITE; exit 99; }
nand_do_flash_file() { record flash; [ "$fault" != flash ]; }
lyw_verify_written() { record verify; [ "$fault" != verify ]; }
nand_do_restore_config() { record restore; [ "$fault" != restore ]; }
sync() { :; }
umount() { record unmount; }
reboot() { record reboot; exit 0; }
nand_do_upgrade_failed() { record failed; exit 91; }
lyw_nand_upgrade /unused/image.bin
TEST
 status=$?
 set -e
 if [ "$fault" = none ]; then
  [ "$status" = 0 ]
  expected=$'image\nflash\nverify\nrestore\nunmount\nreboot'
 else
  [ "$status" = 91 ]
  case "$fault" in
   image) expected=$'image\nfailed' ;;
   flash) expected=$'image\nflash\nfailed' ;;
   verify) expected=$'image\nflash\nverify\nfailed' ;;
   restore) expected=$'image\nflash\nverify\nrestore\nfailed' ;;
  esac
 fi
 [ "$(cat "$trace")" = "$expected" ]
 echo "PASS $fault: $(tr '\n' ' ' < "$trace")"
 rm "$trace"
done
