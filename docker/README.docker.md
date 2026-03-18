# Docker 构建目录说明

此目录用于存放 Docker 构建时需要的大型安装包（已在 `.gitignore` 中排除）。

放置海康 MVS SDK 安装包，文件名以 `MVS` 开头即可：

- `MVS*.deb`：新版 SDK（v4.x，推荐）
- `MVS*.tar.gz`：旧版 SDK（v3.x）

下载地址：[Hikrobot MVS Linux x86_64](https://www.hikrobotics.com/cn2/source/support/software)

路径：Machine Vision → MVS → Linux x86_64

## 海康 USB 相机（Docker 开发）宿主机前置设置

### 1) 提升 usbfs 内存（解决 `start grab` 的 `0x80000006`）

```bash
echo 2000 | sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb
cat /sys/module/usbcore/parameters/usbfs_memory_mb
```

建议持久化（GRUB）：

```bash
sudo sed -i 's/^GRUB_CMDLINE_LINUX="\(.*\)"/GRUB_CMDLINE_LINUX="\1 usbcore.usbfs_memory_mb=2000"/' /etc/default/grub
sudo update-grub
sudo reboot
```

### 2) 配置 udev 权限（避免每次手动 chmod USB 节点）

```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="2bdf", MODE="0666"' | sudo tee /etc/udev/rules.d/99-hikrobot-usb.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

> `2bdf` 是 Hikrobot USB 设备常见 Vendor ID。

### 3) 启动开发容器

```bash
set -a && source .env && set +a
export LOCAL_UID=$(id -u) LOCAL_GID=$(id -g)
docker compose --project-directory . -f docker/compose.dev.yml up -d
```

当前 `compose.dev.yml` 已包含：

- `devices: /dev/bus/usb`
- `privileged: true`
- `group_add: ["0"]`（允许非 root 用户访问 `root:root 0664` 的 USB 节点）

## 容器内 MVS 启动排障

如果出现：

- `./MVS: error while loading shared libraries: libMVRender.so`
- `Could not load the Qt platform plugin "xcb"`

先在容器内执行：

```bash
cd /opt/MVS/bin
./MVS.sh
```

不要直接运行 `./MVS`（它不会自动注入 MVS 自带库路径）。

若仍失败，排查命令：

```bash
export LD_LIBRARY_PATH=/opt/MVS/bin:/opt/MVS/lib/64:/opt/MVS/lib:${LD_LIBRARY_PATH}
ldd /opt/MVS/bin/QtPlugins/platforms/libqxcb.so | grep "not found"
QT_DEBUG_PLUGINS=1 /opt/MVS/bin/MVS.sh
```

本仓库镜像已补齐常见缺失依赖（含 `libxi6`、`libxrender1`）。
