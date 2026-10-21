# LYW-30M OpenWrt：双频 Wi-Fi 6、NSS 加速与免拆机刷机教程

把中国移动定制的岭雁 **LYW-30M** 改成一台可以自行维护的 OpenWrt 路由器，是这个分支的目标。现在，原厂 Web 开启 SSH、安装专用不死 U-Boot、网页刷入 OpenWrt，以及系统内升级这条流程已经在实机跑通。

本项目针对 **AX3000_Q06_V2.0_0223 / IPQ5018 / 256MiB RAM / 128MiB SPI NAND** 做适配。当前发布 **NAND24**：Linux **6.18.55**，NSS Firmware **12.5-210-MP**，双频 ath11k Wi-Fi NSS Offload。系统核心来自 OpenWrt NSS 分支，软件包和 LuCI 使用固定版本的 ImmortalWrt feeds。

[下载 OpenWrt 固件](https://github.com/Jioyzen/openwrt-nss-edma/releases/tag/lyw-30m-nand24) · [下载专用不死 U-Boot](https://github.com/Jioyzen/uboot-qsdk12.5-build/releases/tag/lyw-30m-web-20261020) · [构建与技术说明](README.LYW-30M.md) · [NAND24 验收记录](devices/lyw-30m/docs/nand24-validation.zh-CN.md)

## 这套固件为 LYW-30M 做了什么

### 让无线转发真正用上 NSS

IPQ5018 的两个 Cortex-A53 核心承担双频无线与网络协议栈时，纯软件转发容易先碰到 CPU 瓶颈。本分支沿用社区的 Linux 6.18 NSS 方案，在主线 `stmmac` / `dwmac-ipq5018`、`qca8k` / DSA 上接入 NSS，并适配 **ath11k 双频 Wi-Fi 卸载**，不依赖旧版 SSDK / qca-nss-dp 以太网栈。

本机此前在 5GHz、合适终端与射频设置下，用户实测吞吐接近千兆有线回程上限，CPU 占用也明显降低。NAND24 对应的 RAM34 候选再次通过用户吞吐测试。这些是本机测试结果；终端、距离、干扰和频宽仍会影响实际速度，出厂默认 HE80 也不等于开发测试中的 HE160。

### 让 256MiB 内存用得更合理

保留已验证的 **NSS LOW Profile、ath11k 256M Profile 和 16MiB NSS 预留**，配套 pbuf、DMA / 缓冲处理及驱动检查，避免仅为提高空闲数字盲目缩减无线资源。8MiB NSS 预留曾有吞吐回退，本版没有采用。

NAND24 从闪存启动、双频和 NSS 初始化后的可用内存快照约 **43.5MiB**。这是轻载快照，不是无线满负载最低值。物理内存仍是 256MiB；无线/NSS/安全固件预留及内核开销使 Linux 的 `MemTotal` 约为 163.6MiB，并非少识别了内存。

固件裁剪本机没有的 MMC/eMMC、USB 及纯 USB PHY 支持，使用 `ip-tiny`，去掉 `ip-full` / `libbpf` / `libelf` 依赖和无用 RMNET 支持。共享 UNIPHY、无线、以太网、NAND 及必要诊断能力保留。

### 保留完整的基础路由体验

- 双频 Wi-Fi 6，四个千兆网口按外壳 WAN / LAN1 / LAN2 / LAN3 对应。
- 防火墙、NAT、DHCP/DNS、PPPoE、IPv6、VLAN 和软件包管理；默认标准路由模式，也可自行配置 AP。
- 简体中文、Argon 主题、上海时区、国内 NTP，Web 使用 **80** 端口。
- LuCI NSS 状态页及温度显示；状态页不额外运行采集守护进程。
- 红/绿状态灯适配，通过链路、路由通知更新状态，不运行周期性联网探测；指示灯不保证公网业务一定可达。
- **119MiB 单系统 UBI**，安装实例中可写数据空间余量约 85MiB；保留引导链、环境及本机校准区。
- 原厂 BDF 板级射频数据适配；ART/caldata 从每台机器自身的分区读取，不用其他型号的校准数据替代。

## 开始前，先认准硬件和文件

本项目实测硬件如下。相同外壳名称不能代替板号、闪存及分区核对。

| 项目 | 实测配置 |
|---|---|
| 设备 / 主板 | 岭雁 LYW-30M / AX3000_Q06_V2.0_0223 |
| SoC | Qualcomm IPQ5018，MP03.3 |
| 无线 | IPQ5018 内置 2.4GHz；5GHz 芯片丝印 QCN6102，驱动使用 QCN6122 固件目录 |
| 交换机 | QCA8337 |
| 内存 / 闪存 | 256MiB DDR / Winbond W25N01GW 128MiB SPI NAND |
| NAND 几何 | 2048 字节页、64 字节 OOB、ECC4、128KiB 擦除块 |
| 原厂软件样本 | Linux 4.4.60，2023-02-24 版本 U-Boot |

去 Releases 下载文件，先看用途，再看后缀：

| 文件 | 应该在哪里使用 |
|---|---|
| `lyw-nss618-nand24-squashfs-sysupgrade.bin` | **已经运行本机适配 OpenWrt** 时，在 LuCI“备份与升级”中升级 |
| `lyw-nss618-nand24-squashfs-factory.ubi` | **专用不死 U-Boot 的“固件更新”网页**，首次安装或恢复 OpenWrt |
| `lyw-30m-uboot-web-20261020-appsbl-0x140000.bin` | 原厂 SSH 首次安装引导程序，已补齐至本机主 APPSBL 的 1.25MiB |
| `lyw-30m-uboot-web-20261020.bin` | 640KiB 原始 U-Boot 镜像；已有专用恢复 Web 时用于“U-Boot 更新” |
| `SHA256SUMS` | 对应 Release 内下载文件的 SHA256 校验值 |

**factory 与 sysupgrade 不能互换；U-Boot 镜像也不能上传到“固件更新”。** 其他路由器的 OpenWrt 镜像即使同为 IPQ5018，也不能代替本机固件。原厂 Web 的普通升级页不接受这里的 factory / sysupgrade。

以下电脑端命令按 Linux / WSL 的 Bash 编写。下载后，在各自文件夹执行 `sha256sum -c SHA256SUMS` 校验；只下载部分附件时，核对其中相应文件的结果即可。

## 第一步：从原厂隐藏页面开启 SSH

电脑用网线连接 **LAN3**，先登录原厂管理页面，确认路由器当前 IP。实测干净原厂系统地址为 `192.168.10.1`，修改过地址或由 DHCP 获得地址的机器，以实际地址为准。

浏览器打开：

```text
http://路由器当前IP/itms/set/telnet
```

页面标题是“Telnet_SSH管理”。将 **SSH 开启、Telnet 关闭**，省份保留页面当前值，输入本机普通 **user 管理账号的密码** 后提交。密码直接输入，页面会自行编码，不要手工 Base64 后再填入。

看到“操作成功”后，在电脑终端连接：

```sh
ssh root@192.168.10.1
```

这里有两个不同的密码：**隐藏页面校验 user 密码，SSH 登录使用原厂 root 密码**。它们也都不是新 OpenWrt 的 `password`。本版原厂固件的 root 初始口令可从对应 rootfs 的 `/etc/uci-defaults/z_ctcapd` 中 `PASSWORD_ROOT` 变量核实；项目不发布单台机器的管理凭据。

如果手头已有匹配的原厂 SquashFS，可在电脑离线查看该变量，无须先获得 SSH：

```sh
unsquashfs -cat original-rootfs.squashfs etc/uci-defaults/z_ctcapd | sed -n '/^PASSWORD_ROOT=/p'
```

原厂 UBI 升级包应先提取其中的 `ubi_rootfs` 卷，不能直接把整个 UBI 文件当 SquashFS。不同固件版本可能更改 root 口令；没有对应口令或可解包的匹配固件时，此处尚不具备 SSH 登录条件，不能把“开启端口”当作“已经拿到 root”。

如 OpenSSH 明确提示 `ssh-rsa` 主机密钥协商失败，可为该次连接添加 `-o HostKeyAlgorithms=+ssh-rsa`。登录后运行 `id`，应看到 `uid=0(root)`。

这条路径是有密码校验的原厂隐藏管理功能。实机已验证错误 user 密码被拒、正确密码开启 SSH，以及重启后 SSH 保持开启，**开启 SSH 不需要拆机接 TTL**。

## 第二步：备份本机，再核对引导分区

在原厂 SSH 中先检查：

```sh
cat /proc/mtd
cat /proc/cmdline
uname -a
fw_printenv bootcmd
```

原厂预留了主 `0:APPSBL` 和备用 `0:APPSBL_1`。本机主分区为 `mtd11`、大小 `0x140000`，从主 APPSBL 启动；备用区全为 `0xff`，**没有可用的备用 U-Boot**。其他机器要按分区名称及实际启动选择核对，不能直接照抄 `mtd11`，更不能为了安装而改写 BOOTCONFIG。

建议先在电脑端保存所有 MTD 主数据区备份，避免把大备份放到路由器 `/tmp` 中。以下命令在**电脑 Bash**执行，将 IP 改成原厂当前地址：

```bash
router_ip=192.168.10.1
backup_dir="lyw-30m-stock-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
ssh "root@$router_ip" 'cat /proc/mtd' > "$backup_dir/proc-mtd.txt" || exit 1
ssh "root@$router_ip" 'cat /proc/cmdline; fw_printenv' > "$backup_dir/boot-env.txt" || exit 1

while read -r part; do
    ssh "root@$router_ip" "cat /dev/$part" > "$backup_dir/$part.bin" || exit 1
    remote_hash=$(ssh "root@$router_ip" "sha256sum /dev/$part" | awk '{print $1}')
    local_hash=$(sha256sum "$backup_dir/$part.bin" | awk '{print $1}')
    [ "$local_hash" = "$remote_hash" ] || exit 1
    echo "已校验 $part"
done < <(awk -F: '/^mtd[0-9]+:/ {print $1}' "$backup_dir/proc-mtd.txt")
```

这里读到的是经 NAND 驱动 ECC 纠正后的主数据，不包含 OOB，不是可跨机器恢复的通用整片镜像。备份保留在自己的电脑，尤其不要把 ART、环境和个人配置上传到公共仓库。后续写入只针对已确认的主 APPSBL；SBL1、MIBIB、BOOTCONFIG、ART 和备用 APPSBL 均不写。

## 第三步：通过原厂 SSH 安装专用不死 U-Boot

已经安装本项目对应 U-Boot 的机器，直接跳到下一步，不必重复写引导程序。

确认本机硬件、NAND/ECC、主 APPSBL 启动选择及备份后，在**电脑端**上传补齐版本：

```sh
ssh root@192.168.10.1 \
    'cat > /tmp/lyw-30m-uboot-appsbl.bin' \
    < lyw-30m-uboot-web-20261020-appsbl-0x140000.bin
```

再登录**原厂 SSH**，执行下列检查与写入。任何一步失败都停止，不要跳过检查继续执行：

```sh
set -e
image=/tmp/lyw-30m-uboot-appsbl.bin
expected=5080d91cb41dace19781053b72a1b0978cf97a77f397cbb3c56af2ccd1e85d87
part=$(awk -F '"' '$2 == "0:APPSBL" { split($1, p, ":"); print p[1] }' /proc/mtd)
case "$part" in
    mtd[0-9]|mtd[0-9][0-9]) ;;
    *) echo '未能唯一识别主 APPSBL，停止'; exit 1 ;;
esac
[ "$(cat "/sys/class/mtd/$part/name")" = '0:APPSBL' ]
[ "$(cat "/sys/class/mtd/$part/size")" = 1310720 ]
[ "$(cat "/sys/class/mtd/$part/ecc_strength")" = 4 ]
[ "$(cat "/sys/class/mtd/$part/ecc_failures")" = 0 ]
[ "$(cat "/sys/class/mtd/$part/bad_blocks")" = 0 ]
[ "$(fw_printenv -n bootcmd)" = bootipq ]
[ "$(wc -c < "$image")" -eq 1310720 ]
[ "$(sha256sum "$image" | awk '{print $1}')" = "$expected" ]

mtd -f write "$image" "/dev/$part"
sync
[ "$(sha256sum "/dev/$part" | awk '{print $1}')" = "$expected" ]
[ "$(cat "/sys/class/mtd/$part/ecc_failures")" = 0 ]
echo '主 APPSBL 整分区读回一致'
```

这是已验证原厂布局的主分区安装方法。若实际分区大小、ECC、启动命令或启动选择不同，不应强行套用。原厂 `mtd` 工具会把 `0:APPSBL` 中的冒号当多设备分隔符，因此命令使用核对后的 `/dev/mtdX`，不把分区名称直接传给 `mtd`。`-f` 是该版工具写引导镜像所需参数，不是绕过前置核对的理由。

完整读回一致后，设置一次性进入恢复 Web。仍在**原厂 SSH**执行：

```sh
fw_setenv failsafe 1
[ "$(fw_printenv -n failsafe)" = 1 ] || exit 1
[ "$(fw_printenv -n bootcmd)" = bootipq ] || exit 1
sync
reboot
```

无需先手工设置 OpenWrt 启动命令。新 U-Boot 会消费 `failsafe=1` 进入网页；成功刷入 factory 后才迁移必要启动变量。

## 第四步：在不死 U-Boot 网页刷入 OpenWrt

重启后，电脑仍接 **LAN3**，将电脑网卡暂设为 `192.168.1.2/24`，无需配置网关，浏览器打开：

```text
http://192.168.1.1/firmware.html
```

在 **“固件更新”** 中选择 `lyw-nss618-nand24-squashfs-factory.ubi`，等待上传、校验，通过后执行刷写。写入完成再重启，过程中不要断电。

专用 U-Boot 会检查 UBI 几何、CRC、卷结构、FIT 的 `config@mp03.3`、本机板型及 NAND profile。factory 成功写入后，自动保存 `lyw_mtd`、`lyw_args`、`lyw_boot` 和 `bootcmd`，让 OpenWrt 使用从 `0x00900000` 开始、119MiB 的单系统区；MIBIB、BOOTCONFIG 和校准区保持原有内容，不需要另刷分区表。

如果提示 `invalid_factory_firmware`，核对下载文件、SHA256 和 U-Boot 版本，查看响应中的 `reason`；不要强制刷入 sysupgrade 或其他机型镜像。当前发布 U-Boot 与 NAND24 factory 已通过真实校验源码的九项主机回归；完整原厂到恢复 Web 刷写流程此前使用 NAND23 在本机验证，NAND24 则已通过系统内升级及 NAND 启动验收。

## 第五步：第一次登录和上网配置

刷入 factory 后，将电脑网卡改回 DHCP 自动获取，或临时设为 `192.168.2.2/24`，访问 **http://192.168.2.1**。

| 项目 | 镜像初始值 |
|---|---|
| 用户名 / 密码 | `root` / `password` |
| 管理地址 / Web 端口 | `192.168.2.1/24` / `80` |
| WAN / WAN6 | DHCP / DHCPv6 |
| LAN | LAN1、LAN2、LAN3 与 Wi-Fi 桥接，提供 DHCP |
| 2.4GHz / 5GHz SSID | `LYW-2.4G` / `LYW-5G` |
| Wi-Fi 加密 | 开放，不加密 |
| 国家 / 信道 / 功率 | CN / auto / 驱动和监管域默认值 |
| 初始频宽 | 2.4GHz HE20；5GHz HE80 |
| 界面 / 时区 | 简体中文 Argon / Asia/Shanghai |

在“网络 → 接口”设置上网方式，在“网络 → 无线”设置加密、信道和频宽。路由模式下，上级网络与 LAN 应使用不同网段；如果上级也是 `192.168.2.0/24`，先调整 LAN 网段。NSS 页面可查看卸载状态，SSH 执行 `nss-status` 可看更完整诊断。

上表是**全新安装或不保留配置升级**的默认值。保留配置升级会继续使用自己的 IP、Wi-Fi 和密钥。本项目开发机保留了 `192.168.2.251`，它不是发布镜像的初始地址。OpenWrt 没有通用 `htmode=auto`，所以只把信道设为自动，频宽明确为 HE20 / HE80。

## 以后升级与恢复怎么做

已经运行本项目单系统 OpenWrt 时，在“系统 → 备份与升级”上传 **`sysupgrade.bin`**，按需保留配置。普通系统升级不用重刷 U-Boot；固定版本内核模块应与本仓库配套构建，不要混装公共 snapshot 的其他内核模块。

系统无法进入时，专用 U-Boot 的恢复网页可以重新写入 factory。本版 OpenWrt 没有预装 `uboot-envtools` 或环境分区配置；不能直接照抄原厂的 `fw_setenv` 命令。若已自行准备匹配工具并核对 `/etc/fw_env.config` 正确指向本机环境分区，可通过 `fw_setenv failsafe 1`、`sync`、`reboot` 设置一次性恢复 Web；TTL 中执行 `httpd` 也可进入已验证的恢复入口。

Reset 上电入口已在代码中适配，但尚无独立记录覆盖物理按键和真正断电启动的全部组合；完整测试记录以一次性 failsafe / 软件重启进入 Web 为准。“不死”依赖引导链完整，也没有“Linux 启动失败必然自动进入 Web”的保证，不能恢复被破坏的 SBL1、MIBIB 或 ART。

## 当前完成度与后续维护

NAND24 已完成整镜像构建、写后 kernel/rootfs 校验、15 个保护分区校验、配置保留、双频 NSS、Web/温度及自动软件重启验证；ECC 失败/纠正和坏块均为 0，检查窗口未见 OOM、panic 或页分配失败。

仍需跟踪高负载 NSS RX 描述符累计计数，以及反复人工触发无线固件崩溃后的 CE/HTT/skb 恢复问题；没有把正常吞吐通过写成所有故障恢复已解决。原厂安全固件的 PSCI 提示等兼容日志仍在，24 小时负载、完整 WAN/NAT/PPPoE 压测及跨机器复现范围也不能扩大解释。详情见 [NAND24 验收](devices/lyw-30m/docs/nand24-validation.zh-CN.md) 与 [构建清单](devices/lyw-30m/builds/nand24.json)。

想自行构建或继续移植，阅读 [README.LYW-30M.md](README.LYW-30M.md)：锁定的上游/feeds、板级 DTS、配置、必要 BDF 输入及构建方法都在其中。系统与 U-Boot 分仓维护，公共源码不包含单台机器的 ART、备份、SSH 密钥或管理凭据。

## 来源与致谢

系统开发上游为 [kuncy7/openwrt-nss-edma / c3po-tag-8021q](https://github.com/kuncy7/openwrt-nss-edma/tree/c3po-tag-8021q)，NSS 配套来自 [kuncy7/nss-packages](https://github.com/kuncy7/nss-packages/tree/ipq50xx-rebase)。该项目在主线以太网栈上实现 IPQ5018 NSS，为本机移植提供了基础；[上游技术文档](README.ipq50xx.md)、[上游原始 README](README.upstream.md) 和 [社区讨论](https://forum.openwrt.org/t/ipq5018-nss-offload-on-kernel-6-18-with-the-upstream-ethernet-stack-gl-b3000/253014) 保留供参考。

不死 U-Boot 来自 [chenxin527/uboot-qsdk12.5-build](https://github.com/chenxin527/uboot-qsdk12.5-build)，本机适配独立维护于 [Jioyzen/uboot-qsdk12.5-build](https://github.com/Jioyzen/uboot-qsdk12.5-build/tree/lyw-30m-recovery)。感谢 OpenWrt、ImmortalWrt、Julius Bairaktaris、kuncy7、George Moussalem、Robert Marko、qosmio、chenxin527 及相关社区开发者。

源码许可见 [LICENSES/GPL-2.0](LICENSES/GPL-2.0)；各组件和厂商固件保留其各自许可。
