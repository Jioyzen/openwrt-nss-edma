include $(TOPDIR)/rules.mk

ARCH:=aarch64
BOARD:=qualcommax
BOARDNAME:=Qualcomm Atheros 802.11ax WiSoC-s
FEATURES:=squashfs ramdisk fpu nand rtc emmc
KERNELNAME:=Image
CPU_TYPE:=cortex-a53
SUBTARGETS:=ipq807x ipq60xx ipq50xx

KERNEL_PATCHVER:=6.18

include $(INCLUDE_DIR)/target.mk

# This kernel is shared by every selected image. Apply board-only hardware
# exclusions solely to a single LYW-30M profile, never a multi-device build.
ifeq ($(CONFIG_TARGET_qualcommax_ipq50xx),y)
ifeq ($(CONFIG_TARGET_MULTI_PROFILE),)
ifneq ($(filter "DEVICE_lingyan_lyw-30m-single" "DEVICE_lingyan_lyw-30m-ram",$(CONFIG_TARGET_PROFILE)),)
LINUX_KCONFIG_LIST += $(TOPDIR)/devices/lyw-30m/kernel-no-external-io.config
endif
endif
endif

DEFAULT_PACKAGES += \
	kmod-usb3 kmod-usb-dwc3 kmod-usb-dwc3-qcom \
	kmod-leds-gpio kmod-gpio-button-hotplug \
	kmod-ath11k-ahb \
	wpad-basic-mbedtls uboot-envtools \
	e2fsprogs kmod-fs-ext4 losetup

$(eval $(call BuildTarget))
