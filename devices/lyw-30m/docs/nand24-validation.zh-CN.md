# NAND24 维护版本验收

2026-10-21，将用户确认吞吐正常的RAM34固化为NAND24。源码提交为 `b93d34a206b4054ec2cd715bae7ff231f79c9dd2`；其后的发布记录提交不更改运行内核或驱动。镜像大小、SHA256与结构化验收见 [构建清单](../builds/nand24.json)。

## 本轮累计变更

- 收录本地已验收的RSSI、重试、64位流量统计及BA窗口上报修复，统计消息与QMI/AFC内存请求边界检查，以及RCU/DFS相关修正。
- 保持NSS 12.5匹配驱动与统计ABI、16MiB预留、LOW/ath11k 256M预算；QCN6122软件RX描述符请求2048，初始化ACK通过。没有继续缩保留内存或盲目缩Ring。
- 单设备板级配置移除本机没有的MMC/SDHCI和纯USB PHY支持，保留共享UNIPHY、NAND、以太网和无线。与此前内核相比MemTotal增加256KiB。
- 使用ip-tiny，移除ip-full/libbpf/libelf依赖和无用RMNET支持；保留防火墙、NAT、DHCP/DNS、PPPoE、IPv6、软件包管理、中文Argon和只读NSS状态页，状态页不新增常驻服务。
- 加入实际rootfs包、依赖与模块审计工具，以及锁定的NSS driver/clients修复。RAM33未通过重复故障恢复验证的三份候选补丁未纳入。

以上为NAND23之后的累计维护变更，不将每项防御性修正等同于已复现并根治一个实机故障。无线吞吐使用用户对RAM34的正常结果，未冒充NAND24安装后的新测速。

## 构建与写入

12线程完整构建成功，构建输入指纹一致。FIT、UBI几何/CRC/容量、默认配置、固件、必要升级工具和私钥排除检查通过；66个模块/启动脚本与RAM34一致。NAND内核配置相对RAM34仅改变initramfs相关项。公开配置使用源码内工具链，实际本机镜像沿用既有构建工具链；保留完整本地配置/源码快照，不承诺跨工具链逐字节一致。

写前保存128MiB ECC纠正后整片备份、逐分区hash、NAND23镜像及RAM34配置。由NAND23执行原生sysupgrade，只更新既有119MiB UBI系统区。kernel与rootfs payload读回一致，15个引导/环境/校准保护分区hash未变，未改写U-Boot或启动环境。

公开镜像首次启动仍使用标准路由默认值：LAN 192.168.2.1、WAN DHCP、root/password、开放的LYW-2.4G与LYW-5G、自动信道、HE20/HE80和默认功率。此次实机升级明确保留已核对的开发配置，因此管理地址仍为192.168.2.251。

## 实机检查

- 首次NAND启动和一次自动软件重启均验证为SquashFS /rom + UBIFS /overlay，无RAM根文件系统。
- 两路AP ENABLED，ath11k双频NSS生效；NSS12.5启动、802816字节extra_pbuf、16336 high-water、2048 RX描述符请求ACK正常。
- HTTP80、温度读取与配置/SSH密钥保留通过；只有mtd15可写，其余15个分区只读。
- UBI kernel 32 LEB、rootfs 73 LEB、rootfs_data 821 LEB，保留provisioning卷；overlay可用约85.2MiB。
- 两次检查均ECC失败0、纠正0、坏块0，无OOM、WARN/Oops/panic或page allocation failure。

| 内存项 | 首次启动KiB | 软件重启后KiB |
|---|---:|---:|
| MemTotal | 167548 | 167548 |
| MemAvailable | 42140 | 44508 |
| Shmem | 288 | 260 |
| Slab | 40912 | 39944 |
| SUnreclaim | 33760 | 33428 |

这些是功能检查后的快照，不是同负载内存收益对照，也不是最低可用内存保证。重启初期的检查脚本曾在debugfs文件出现前退出，双频随后正常初始化，等待就绪后完整只读复核通过；没有为此重刷或变更驱动。

## 尚存限制

高负载NSS RX描述符失败累计计数仍未证明根治；人工连续触发无线固件崩溃后的CE/HTT/skb释放故障仍未解决。正常吞吐验收不覆盖这种故障恢复路径。

日志仍有原厂安全固件PSCI PC mode -1、/init探测、overlay UUID及外置模块taint等兼容提示；未接WAN时dnsmasq无上游符合接线条件。AFC type10已按本机8192字节请求在m3-dump范围内分配，不再简单忽略该请求。没有因消除提示而改写安全固件、校准数据或保留内存。

此次未新增NAND版客户端吞吐、24小时负载、物理断电和完整WAN/NAT/PPPoE压测。NAND23完整备份、镜像及专用U-Boot恢复路径继续保留。
