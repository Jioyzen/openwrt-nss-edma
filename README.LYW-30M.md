# LYW-30M 专用 OpenWrt NSS 分支

本分支维护岭雁 LYW-30M / AX3000_Q06_V2.0_0223 的 IPQ5018、256MiB RAM、128MiB SPI NAND、QCA8337 和双频 ath11k 适配。

## 来源与当前设备版本

- 开发上游：[kuncy7/openwrt-nss-edma](https://github.com/kuncy7/openwrt-nss-edma/tree/c3po-tag-8021q)，分支 `c3po-tag-8021q`。
- 固定上游基线：`33ff647739f1f556556a0340afc3438dc85afc38`。
- 当前已安装 NAND24 源码提交：`b93d34a206b4054ec2cd715bae7ff231f79c9dd2`；镜像SHA和实机验收见 `devices/lyw-30m/builds/nand24.json`。NAND23仍保留作恢复基线。
- NAND22回退基线提交：`c1b1c67a80ebb4350565f3e3f3c00a94f6683671`，继续保留。
- Linux 6.18.55，NSS Firmware 12.5-210-MP，NSS LOW / ath11k 256M profile，16MiB NSS reserved-memory。
- 软件包和 LuCI 来自锁定的 ImmortalWrt feeds；系统核心是 OpenWrt NSS，不能称为完整 ImmortalWrt master。
- 本分支在上述已安装提交之后补充维护文件；分支 HEAD 与路由器上运行的二进制版本分别记录。

GitHub 将本仓库归入 `openwrt/openwrt` fork 网络；实际开发上游是 kuncy7 分支。原 `Jioyzen/openwrt` 地址现重定向到本仓库，旧 `lyw-30m-6.12.80` 分支仍保留。

## 构建

使用满足 OpenWrt 构建依赖的 Linux 主机和新的工作目录：

```sh
git clone --branch lyw-30m-nss125-validation --single-branch https://github.com/Jioyzen/openwrt-nss-edma.git
cd openwrt-nss-edma
./devices/lyw-30m/prepare-feeds.sh
python3 devices/lyw-30m/prepare-overlay.py /absolute/path/to/private-bdf-root
cp configs/lyw-30m-nand24.config .config
make defconfig
make download -j8
make -j"$(nproc)"
```

`prepare-feeds.sh` 固定 packages、LuCI、NSS 三个提交，核对 SHA 并放入五项本机 NSS driver/clients 修复；不会使用构建主机上的绝对路径。`source-lock.json` 记录来源和补丁校验值。重复执行允许相同补丁，遇到冲突停止。

镜像应在完整 `make` 成功后验收；单独执行 `target/install` 不能证明软件包已全部编译和安装。将实际候选 SquashFS 解包后，运行 `python3 devices/lyw-30m/verify-rootfs.py /path/to/extracted-root /path/to/device.manifest` 检查必要软件包、无线/NSS 文件、模块内核版本和本机 BDF。此检查通过后仍须验证 FIT、分区策略和实机运行，不能凭镜像大小或 Kconfig 选择认定可用。

选中单设备 LYW-30M profile 后，`make` 自动把版本化的 `devices/lyw-30m/overlay/` 加入镜像，并把其内容计入根文件系统缓存校验。无需手工复制初始配置。`prepare-overlay.py` 仅放入本地 BDF；显式放在 `files/` 的自定义文件仍按 OpenWrt 惯例覆盖默认值。多设备批量 profile 不自动套用这套板级默认文件。

单设备 LYW-30M 的 RAM 与 single profile 同时使用 `devices/lyw-30m/kernel-no-external-io.config`，裁剪本机没有的 MMC/eMMC、USB 支持及纯 USB PHY 驱动。PCIe/USB 共用 UNIPHY、以太网、NAND、校准数据和无线相关支持保留。内核由同一批镜像共享，因此多设备构建不应用此裁剪片段；内核配置改变后，应重新构建并配套安装内核模块。

`private-bdf-root` 只需包含以下两个从本机原厂数据准备的文件，不能拿其他设备的 ART/caldata 替代：

```text
lib/firmware/ath11k/IPQ5018/hw1.0/board-2.bin
lib/firmware/ath11k/QCN6122/hw1.0/board-2.bin
```

板载 5GHz 芯片曾标识为 QCN6102；当前已验证驱动使用 QCN6122 固件目录。ART 校准数据由板级 hotplug 从本机 `0:ART` 提取。仓库不分发 BDF、ART、MAC、密码哈希、SSH 密钥和个人网络配置。

完整公开 NAND24 配置保留标准路由功能和已验证的精简项，并移除本机外置工具链路径，改用源码内工具链。`configs/lyw-30m-nss125-router.config` 是精简功能片段。公开 overlay 提供简体中文、Argon、上海时区、国内 NTP、NSS 模式和 LED 通知脚本；LED 只观察链路/路由通知，不发送探测包，不能据此证明公网真正可达。HTTP 默认 80，初始账户 `root` / `password`，LAN 地址为 `192.168.2.1/24`，LAN1/2/3 和 Wi-Fi 桥接并提供 DHCP，WAN 为 DHCP、WAN6 为 DHCPv6。SSH 仅在 LAN 提供密码登录，主机密钥首次启动生成。

公开初始 Wi-Fi：2.4GHz `LYW-2.4G`、5GHz `LYW-5G`，均开放不加密，国家 CN、信道 auto、不指定 txpower。频宽采用上游 Wi-Fi 6 初始值 HE20 / HE80；OpenWrt 没有通用的 `htmode=auto`。保留每频段最多 32 个客户端的低内存设备预算。新默认值不复制旧 NAND22 的 AP 地址、上级网关、无线密码或固定射频参数；保留配置升级仍以用户备份为准。

这是一套可移植的构建输入，不是 NAND22 的逐字节重建承诺：原镜像还使用了私有网络覆盖配置、外置 GCC 14.3.0 工具链及本机签名材料。已在独立目录验证锁定 feeds 的获取、锁定补丁校验、overlay 重复生成和 `make defconfig`；展开后启用的软件包清单没有增减。NAND23已用版本化默认配置完成整镜像构建、原厂Web开SSH、专用U-Boot Web刷写和实机启动验收；安装二进制仍使用构建主机既有工具链，未承诺公开配置切换源码内工具链后的逐字节一致性。请勿将持续变化的公共 snapshot 内核模块直接混装到此固定版本；应从同一源码和配置构建所需模块。

## 镜像与布局

- `lingyan_lyw-30m-single`：当前单系统，UBI 从 `0x00900000` 开始，长度 `0x07700000`（119MiB），保留引导链和校准区域；输出位于 `bin/targets/qualcommax/ipq50xx/`。
- 系统内升级使用专用 `sysupgrade.bin`；恢复 Web 使用专用 UBI factory 镜像。两者不能互换。
- 该 profile **不是原厂分区布局的一步转换固件**。原厂机器需要先核实板型、分区、备份、启动命令和 ECC；不能直接把此 sysupgrade 当原厂升级包。
- RAM 诊断 profile：`lingyan_lyw-30m-ram`，启用 initramfs，并取消 single profile。其 NAND 只读策略与 single profile 不同；NSS 可通过 `lyw_nss=off|wired|wifi` 启动参数选择。

专用 U-Boot 独立维护于 [Jioyzen/uboot-qsdk12.5-build](https://github.com/Jioyzen/uboot-qsdk12.5-build/tree/lyw-30m-recovery)。构建系统固件不会更新 U-Boot。

## 已验证与限制

已安装基线完成双频、四口映射、NSS Wi-Fi 桥接、NAND 启动及升级验证；用户报告近距离 5GHz 吞吐接近千兆。8MiB NSS 预留曾出现吞吐回退，因此当前保留 16MiB。长期稳定性、远距离吞吐和每次源码更新后的负载表现仍需分别验证；不承诺零警告或所有标准路由功能均已完成独立压测。

本分支包含本机 DTS、网络/caldata、单系统升级检查、温度读取、内存 profile、ath11k 与 NSS DMA/缓冲修复。NSS feed 的五项本地补丁随系统仓库保存，避免要求第三个维护仓库。上游升级应先固定新 SHA，再检查补丁适用性，完成 RAM 启动和同条件负载对照后发布。

## NAND24 / RAM34 维护更新

`configs/lyw-30m-nand24.config` 是当前维护构建配置，保留标准路由、防火墙、PPPoE、IPv6、Argon/简体中文及只读 NSS 状态页。移除 ip-full/libbpf/libelf 的依赖，使用已验证的 ip-tiny；NSS 状态页无需额外常驻服务。`prepare-feeds.sh` 按锁定清单同步 NSS driver/clients 补丁。

本轮纳入此前本地验证的 RSSI/重试/64位流量统计、AFC请求和统计消息边界检查、RCU和DFS检查等修正；不宣称它们解决高负载 RX 计数或 CE/HTT 缓冲生命周期问题。5GHz QCN6122 NSS 软件 RX 描述符在板级 `etc/modules.conf` 中请求2048，与用户确认吞吐正常的RAM34保持一致；这是固件初始化ACK确认的请求值，非实时池占用读回。

单设备内核裁剪 MMC/SDHCI 和纯 USB PHY 后，RAM34 `MemTotal` 增加256KiB；不是释放NSS或无线保留内存。用户确认RAM34吞吐正常。人工重复触发无线固件故障时仍存在 `skb` 释放崩溃，长期稳定性及完整路由压测没有因此完成。RAM33三份未通过重复恢复验收的候选不纳入本版本。

发布镜像使用上述版本化默认参数；设备升级时可通过经过核对的配置备份保留当前地址、无线及密钥。个人配置和原厂BDF/ART不提交仓库。

NAND24已通过原生sysupgrade写入并完成自动重启验证，kernel/rootfs读回一致、15个保护分区未变、双频NSS/HTTP80及配置保留正常。重启后MemAvailable快照约43.5MiB，不代表无线负载最低值。[NAND24验收记录](devices/lyw-30m/docs/nand24-validation.zh-CN.md)列出具体范围及未解决问题。

## NAND23 首次安装验收

原厂隐藏Web页面开启SSH、原厂SSH刷专用U-Boot、恢复Web刷NAND23已跑通；用户确认系统稳定、初始化及参数正常。实际kernel/rootfs卷与factory一致，13个保护分区未变，只有4个必要启动环境键迁移；ECC失败/纠正及坏块为0。119MiB单系统UBI的数据卷扩到821LEB，初始可写余量约85MiB。

[实测记录及日志分类](devices/lyw-30m/docs/nand23-validation.zh-CN.md) 说明了PSCI/QMI等尚存兼容提示和未独立压测的范围。NSS源补丁已随本仓库固定保存；本次记录更新不改变正在运行的内核、驱动或参数。U-Boot本轮功能源码提交为 `d7daf9fc276b0f910b65ccff168fa3c64dbe7363`，二进制在提交前构建，实际仍显示f687f0a-dirty；安装与恢复步骤由独立U-Boot仓库维护。
