# 岭雁 LYW-30M 刷入 OpenWrt

这篇教程记录如何从中国移动原厂系统开始，开启 Telnet、取得 root、安装专用 U-Boot，再从恢复网页刷入 OpenWrt。完整流程已在 **LYW-30M / AX3000_Q06_V2.0_0223** 上实机验证。

| 下载 | 用途 |
|---|---|
| [OpenWrt NAND24 固件](https://github.com/Jioyzen/openwrt-nss-edma/releases/tag/lyw-30m-nand24) | 恢复网页首次安装用 `factory.ubi`；OpenWrt 内升级用 `sysupgrade.bin` |
| [LYW-30M 专用 U-Boot](https://github.com/Jioyzen/uboot-qsdk12.5-build/releases/tag/lyw-30m-web-20261020) | 原厂 SSH 中安装的 `appsbl-0x140000.bin` |

本机硬件为 IPQ5018、256MiB RAM、QCA8337 和 Winbond W25N01GW 128MiB NAND。外壳、板号或闪存不同的设备不能直接套用本教程。

## 1. 从原厂网页开启 Telnet 和 SSH

电脑网线接路由器 **LAN3**。原厂系统默认管理地址为 `192.168.10.1`；如果已经改过地址，请使用当前地址。暂时拔掉 WAN 网线。

浏览器打开 `http://192.168.10.1/itms/set/telnet`，选择开启 Telnet 和 SSH，省份保持页面原值，在管理密码框输入机身标签上的 `user` 密码，然后提交。

Windows 可用 PuTTY 连接路由器地址，连接类型选 **Telnet**、端口填 **23**。也可以在终端运行：

```sh
telnet 192.168.10.1
```

登录用户名输入 `user`，密码输入机身标签上的密码。输入密码时屏幕不显示字符是正常的。登录后会看到路由器命令提示符。

## 2. 准备一次性 root 脚本

以下命令在 **Telnet 窗口中一条一条执行**。每输入一条按回车，看到提示符后再输入下一条；不要一次粘贴多行。

先保存当前防火墙配置：

```sh
mkdir /tmp/lyw-unlock
```

```sh
cp /etc/config/firewall /tmp/lyw-unlock/firewall.bak
```

逐条创建 root 脚本：

```sh
echo '#!/bin/sh' > /tmp/lyw-unlock/root.sh
```

```sh
echo '[ -f /tmp/lyw-unlock/done ] && exit 0' >> /tmp/lyw-unlock/root.sh
```

```sh
echo "printf 'password\npassword\n' | passwd root > /tmp/lyw-unlock/passwd.log 2>&1 && touch /tmp/lyw-unlock/done" >> /tmp/lyw-unlock/root.sh
```

```sh
chmod 700 /tmp/lyw-unlock/root.sh
```

把这个脚本加入原厂防火墙配置：

```sh
echo "" >> /etc/config/firewall
```

```sh
echo "config include 'lyw_unlock'" >> /etc/config/firewall
```

```sh
echo " option type 'script'" >> /etc/config/firewall
```

```sh
echo " option path '/tmp/lyw-unlock/root.sh'" >> /etc/config/firewall
```

```sh
echo " option reload '1'" >> /etc/config/firewall
```

## 3. 在原厂网页触发脚本

用标签账号登录原厂管理网页，进入 **高级设置 → 端口转发**：

1. 新建一条临时 TCP 端口转发规则。外部端口和内部端口都填 `49152`，内部 IP 填 `192.168.10.254`，保存并应用。
2. 删除刚才这条规则，再保存并应用。

这两次操作会触发原厂防火墙重载。WAN 线保持拔下。

## 4. 登录 root SSH

在电脑另开一个终端，运行：

```sh
ssh -o HostKeyAlgorithms=+ssh-rsa root@192.168.10.1
```

首次连接输入 `yes` 确认主机密钥，密码输入 `password`。这是上一步脚本设置的 root 密码。

登录后运行：

```sh
id
```

看到 `uid=0(root)` 即表示已取得 root。此方法在本机原厂固件上验证成功，不需要原厂 root 密码或 TTL。

恢复原厂防火墙配置并移除临时脚本：

```sh
cat /tmp/lyw-unlock/firewall.bak > /etc/config/firewall
```

```sh
fw3 -q reload
```

```sh
rm -rf /tmp/lyw-unlock
```

root 密码仍为 `password`，后续刷写步骤继续使用这个密码。

## 5. 备份原机分区

在 Windows 搜索并打开 **命令提示符（cmd.exe）**，不要在 Telnet 窗口或 PowerShell 中执行。先保存分区表，再把 16 个 MTD 分区分别导出为文件：

```cmd
mkdir lyw30m-backup
```

```cmd
cd lyw30m-backup
```

```cmd
ssh -o HostKeyAlgorithms=+ssh-rsa root@192.168.10.1 "cat /proc/mtd" > proc-mtd.txt
```

```cmd
for /L %i in (0,1,15) do @ssh -o HostKeyAlgorithms=+ssh-rsa root@192.168.10.1 "cat /dev/mtd%i" > mtd%i.bin
```

每个分区会单独询问一次 root 密码，输入 `password`。完成后检查文件：

```cmd
dir mtd*.bin
```

应看到 `mtd0.bin` 至 `mtd15.bin` 共 16 个文件；文件大小应与 `proc-mtd.txt` 中对应分区的容量相符。

## 6. 安装专用 U-Boot

把 U-Boot Release 中的 `lyw-30m-uboot-web-20261020-appsbl-0x140000.bin` 下载到 `lyw30m-backup` 文件夹，在当前命令提示符中核对 SHA256：

```cmd
certutil -hashfile lyw-30m-uboot-web-20261020-appsbl-0x140000.bin SHA256
```

结果应为 `5080d91cb41dace19781053b72a1b0978cf97a77f397cbb3c56af2ccd1e85d87`。然后从电脑上传镜像：

```cmd
ssh -o HostKeyAlgorithms=+ssh-rsa root@192.168.10.1 "cat > /tmp/lyw-uboot.bin" < lyw-30m-uboot-web-20261020-appsbl-0x140000.bin
```

回到 root SSH 窗口，确认设备主引导分区：

```sh
grep '0:APPSBL' /proc/mtd
```

本机应显示主分区为 `mtd11`，备用分区为 `mtd12`。确认主分区名称和容量：

```sh
cat /sys/class/mtd/mtd11/name
```

```sh
cat /sys/class/mtd/mtd11/size
```

输出应分别为 `0:APPSBL` 和 `1310720`。再确认镜像大小及 SHA256：

```sh
wc -c < /tmp/lyw-uboot.bin
```

```sh
sha256sum /tmp/lyw-uboot.bin
```

大小应为 `1310720`，散列应与上面的值一致。确认后只写主 APPSBL：

```sh
mtd -f write /tmp/lyw-uboot.bin /dev/mtd11
```

写完后读回校验：

```sh
sha256sum /dev/mtd11
```

读回散列必须仍为 `5080d91cb41dace19781053b72a1b0978cf97a77f397cbb3c56af2ccd1e85d87`。设置一次性进入 U-Boot 恢复网页：

```sh
fw_setenv failsafe 1
```

```sh
reboot
```

## 7. 从 U-Boot 恢复网页刷入 OpenWrt

电脑网线仍接 LAN3，将电脑网卡临时设为静态地址 `192.168.1.2`、掩码 `255.255.255.0`，网关留空。浏览器打开：

`http://192.168.1.1/firmware.html`

在“固件更新”页面上传 NAND24 Release 中的 **`lyw-nss618-nand24-squashfs-factory.ubi`**，等待检查完成后开始刷写。刷写期间不要断电。`sysupgrade.bin` 不是首次安装文件，也不要上传 U-Boot 镜像。

下载后可在 Windows 命令提示符核对 factory 文件：

```cmd
certutil -hashfile lyw-nss618-nand24-squashfs-factory.ubi SHA256
```

结果应为 `45e0ec58bd48176eacc4cc2cf1be83649feb4fdc2873745e9610557b7f950594`。

刷写和重启完成后，把电脑网卡改回自动获取地址，打开 `http://192.168.2.1`：

| 设置 | 初始值 |
|---|---|
| 登录 | `root` / `password` |
| 管理地址 | `192.168.2.1`，HTTP 端口 `80` |
| WAN | DHCP；WAN6 使用 DHCPv6 |
| LAN | LAN1、LAN2、LAN3 和 Wi-Fi 桥接，开启 DHCP |
| Wi-Fi | `LYW-2.4G`、`LYW-5G`，默认开放网络 |

首次进入后，可在“网络 → 无线”设置 Wi-Fi 密码，在“网络 → 接口”配置上网方式。

## 以后升级

已经运行本项目 OpenWrt 时，在“系统 → 备份与升级”上传 Release 中的 **`sysupgrade.bin`**。恢复网页使用的 `factory.ubi` 与系统升级使用的 `sysupgrade.bin` 用途不同，不能互换。

## 固件特点

- 面向 LYW-30M 的 IPQ5018、QCA8337、双频 ath11k 与原厂射频校准数据适配。
- Linux 6.18.55、NSS Firmware 12.5-210-MP，支持有线及双频 Wi-Fi NSS 卸载。
- 单系统 UBI 布局；保留引导链与校准分区，其余 NAND 空间供 OpenWrt 使用。
- 含防火墙、NAT、DHCP/DNS、PPPoE、IPv6、简体中文 LuCI 和 Argon 主题。

源码基础来自 [kuncy7/openwrt-nss-edma](https://github.com/kuncy7/openwrt-nss-edma/tree/c3po-tag-8021q)，NSS 软件包来自 [kuncy7/nss-packages](https://github.com/kuncy7/nss-packages/tree/ipq50xx-rebase)。专用 U-Boot 单独维护于 [Jioyzen/uboot-qsdk12.5-build](https://github.com/Jioyzen/uboot-qsdk12.5-build/tree/lyw-30m-recovery)。
