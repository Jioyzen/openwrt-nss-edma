# LYW-30M OpenWrt 维护分支

本分支基于官方 OpenWrt commit `a5c5ca0666533a0af027e73f80fbc94f21be54c3`，
Linux **6.12.80**、mac80211 backports **6.18.7**、ath11k-smallbuffers。
适用硬件：AX3000_Q06_V2.0_0223 / IPQ5018 / QCN6102（驱动识别为 QCN6122）/
QCA8337 / 256MiB RAM / W25N01GW 128MiB NAND。

这是设备移植维护分支，尚未进入 OpenWrt 官方支持列表。它固定已验证基线，
不自动跟随 master，不引入 NSS。后续升级内核、feeds、驱动应分开提交并重新实测。

## 当前验证状态

- production7 已在本机 NAND 单系统运行，已验证原厂 U-Boot 默认启动、
  6→7 sysupgrade、配置和 SSH host key 保留、独立 RAM 恢复镜像启动及返回 NAND。
- 双频 Wi-Fi 6 AP 工作，吞吐由设备所有者实测反馈正常；本仓库不宣称具体吞吐数值。
- 四网口实机映射：WAN=`wan`，LAN1=`lan1`，LAN2=`lan2`，LAN3=`lan3`，全部桥接。
- 全区 UBI 格式化及 64MiB 随机数据跨重启 SHA 校验通过，ECC corrected/failed 均为 0。
- 两频段分别触发固件 assert 后的 userPD 恢复、IRQ/survey 计数及桥接连通已验证。
- production8 已编译但尚未安装；本分支内核/驱动源码与其一致，另整理了公开构建默认值，
  并将 WebUI 端口调整为 80。本分支的公开默认配置尚未重新整镜像实机验证。
- 未完成物理断电恢复和 24 小时压力测试。已知 SSDK port 0 通知及恢复时 regulatory -22
  日志仍保留，当前测试未观察到它们影响端口或双频恢复。

`source-lock.json` 固定源码、feeds、无线固件和工具版本；`SOURCE_SHA256SUMS`
记录与 production8 对应的 16 个移植源码文件，可在仓库根目录执行
`sha256sum -c devices/lyw-30m/SOURCE_SHA256SUMS`。引导文件、公钥、网络密码和板级二进制不在仓库中。

## 构建

使用正常 OpenWrt Linux 构建环境（非 root 用户），先安装官方文档列出的构建依赖。
在全新 checkout 中执行：

```sh
git clone -b lyw-30m-6.12.80 https://github.com/Jioyzen/openwrt.git
cd openwrt
python3 devices/lyw-30m/prepare.py \
  --ipq5018-bdf /private/path/ipq5018-bdwlan.b23 \
  --qcn6122-bdf /private/path/qcn6122-bdwlan.b50
./scripts/feeds update -a
./scripts/feeds install -a
cp devices/lyw-30m/config.full .config
make defconfig
make -j"$(nproc)" V=s
```

这两个 BDF 必须从适用设备的原厂固件/合法备份获得，脚本只接受已验证的哈希。
不提供下载第三方 ART 或写入其他机器校准数据的流程。本机 ART 保留在 NAND，
由 firmware hotplug 按本机分区提取 caldata；BDF 转换不修改 ART。
QCN6122 BDF 只转换已核实的 schema 字节 `0x45c:03→00` 并重算 XOR16 校验。
`ath11k-bdencoder` 随源码保留原许可；来源及哈希记录于锁文件。

`config.full` 保存生产构建的完整配置；`config.seed` 供审阅主要选项。
feeds 全部安装后再覆盖一次 `.config`，避免准备 feed 元数据时丢失 LuCI 等软件包选择。
可通过 `--local-overlay /private/path/overlay` 合并个人配置，放入本地 SSH 公钥等。
`files/`、`.config` 和设备目录下的 `local/` 均不跟踪。脚本拒绝覆盖现有构建配置。
配置和源码可复现不代表不同构建环境生成的整个镜像逐字节一致。

公开默认配置是四口 AP 桥接，管理 IP **192.168.1.1/24**，DHCP 服务关闭，
WebUI **80**，初始用户/密码 **root/password**，SSH 密码登录限 LAN；无线默认禁用，
设置自己的密码后开启。接入已有网络前请设置不冲突的管理 IP、网关和 DNS。
这些是便于公开分发的初始值，正在运行的本机仍保留自己的管理 IP、密钥登录及 Wi-Fi 配置。

输出目录 `bin/targets/qualcommax/ipq50xx/` 中的专用 profile 为
`lingyan_lyw-30m-single`，包含 `squashfs-factory.ubi`、`squashfs-sysupgrade.bin`
和 `initramfs-uImage.itb`。构建后先运行离线校验：

```sh
prefix=bin/targets/qualcommax/ipq50xx/openwrt-qualcommax-ipq50xx-lingyan_lyw-30m-single
python3 devices/lyw-30m/tools/verify-images.py --single \
  "$prefix-squashfs-factory.ubi" "$prefix-squashfs-sysupgrade.bin" /tmp/lyw-image-check
python3 devices/lyw-30m/tools/verify-recovery.py --single \
  "$prefix-initramfs-uImage.itb" /tmp/lyw-recovery-check.json
bash devices/lyw-30m/tools/test-upgrade-single-order.sh \
  devices/lyw-30m/overlay/lib/upgrade/lyw-30m.sh
```

## 单系统存储、升级与恢复

| 物理区间 | 用途 |
| --- | --- |
| `0x0..0x8fffff` | 9MiB 原厂引导链、安全固件、环境、ART、训练数据，Linux 全部只读 |
| `0x900000+0x7700000` | 119MiB 单系统 UBI，kernel/rootfs/rootfs_data |

952 个 PEB，页 2048、OOB 64、擦除块 128KiB、QPIC ECC4/512、IO macro 100MHz。
实机 UBIFS overlay 约 91.7MiB，基础安装后空闲约 86.9MiB。无原厂系统副本或 A/B 槽。
原厂 U-Boot 程序及 MIBIB 保留，已迁移机器使用专用 U-Boot 环境启动全区 UBI。

**factory.ubi 不是原厂 Web 刷机包。** 本仓库的 sysupgrade 只适用于已经迁移为
上述单系统布局且具有专用启动环境的 LYW-30M；不能直接用于原厂或旧双槽布局。
首装需要本机完整备份、TTL/TFTP 恢复验证、ECC 写读验证和专门的迁移流程，
本分支不提供对未知设备一键重分区的脚本。

已迁移机器升级前备份配置和个人数据，上传专用 sysupgrade 文件到 `/tmp`，执行：

```sh
sysupgrade -T /tmp/lyw-sysupgrade.bin
sysupgrade /tmp/lyw-sysupgrade.bin
```

升级后端校验板型、物理分区、ECC 几何、容量、FIT 和 SquashFS，
调用上游 NAND/UBI 流程，读回 kernel/rootfs 的 SHA，再恢复配置并重启。
它不修改引导环境或校准分区。普通 sysupgrade 重建 overlay，并按备份清单恢复配置，
不会自动保留所有额外用户文件；请另行备份这些文件，避免大备份耗尽 256MiB RAM。

没有 A/B 自动回滚。恢复依靠原厂 U-Boot UART + TFTP 加载专用 initramfs，
不需更换所谓“不死 U-Boot”。已迁移机器的启动环境如下，供核对和恢复参考，
不要在未迁移的设备盲目执行 `saveenv`：

```text
bootcmd=run lyw_boot
lyw_mtd=setenv mtdids nand0=nand0; setenv mtdparts mtdparts=nand0:0x7700000@0x900000(rootfs)
lyw_args=setenv bootargs console=ttyMSM0,115200n8 ubi.mtd=rootfs root=/dev/ubiblock0_1 rootfstype=squashfs ro rootwait swiotlb=1
lyw_boot=run lyw_mtd; ubi part rootfs && ubi read 0x44000000 kernel && run lyw_args && bootm 0x44000000#config@mp03.3
```

RAM 恢复时在 U-Boot 设置本地 TFTP 的 `serverip` 和不冲突的 `ipaddr`，网线用 LAN3：

```text
tftpboot 0x44000000 lyw-recovery.itb
setenv bootargs console=ttyMSM0,115200n8 swiotlb=1
bootm 0x44000000#config@mp03.3
```

其中 `lyw-recovery.itb` 为上文校验过的本设备 initramfs 文件，重命名放入 TFTP 目录。
LAN3 在 U-Boot 中首次协商可能需等待几秒重试。RAM 启动不传 `ubi.mtd`，
避免自动挂载 NAND；**RAM 镜像中 rootfs MTD 仍可写**，不可把 RAM 启动等同于写保护。
进入 RAM 后先确认布局、备份和镜像，再按经过核实的修复流程操作。不要 RAW/OOB 回写，
不要改写 U-Boot/MIBIB/ART，不要使用小米 `bootipq`、切槽或他机的刷写命令。
