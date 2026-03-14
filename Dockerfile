# ─────────────────────────────────────────────────────────────
# RZ-Radar-2025  Docker Image
# Base: Ubuntu 22.04 + Mambaforge (CUDA / TRT 来自 conda env)
# MVS SDK: 需在 docker/ 目录下放置 MVS 安装包（见下方说明）
#
# MVS SDK 获取方式：
#   海康官网 → 下载中心 → Machine Vision → MVS SDK
#   Linux 版通常包含 x86_64 的 .deb 或 setup.sh
#   将文件放到 docker/ 目录，文件名以 MVS 开头即可
#
# 支持：
#   .deb 包 (MVS v4+)          → docker/MVS*.deb
#   .tar.gz + setup.sh (MVS v3) → docker/MVS*.tar.gz
# ─────────────────────────────────────────────────────────────

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV MVCAM_COMMON_RUNENV=/opt/MVS/lib
ENV PATH=/opt/conda/envs/RZ_radar-2025/bin:/opt/conda/bin:$PATH

# ── 换清华 apt 源 ─────────────────────────────────────────────
RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list \
    && sed -i 's|http://security.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list

# ── 系统基础依赖 ──────────────────────────────────────────────
# libgl / glib: OpenCV 依赖
# libxcb* / libxkbcommon-x11-0: PyQt6 无 headless 模式
# libusb: MVS USB 相机支持（GigE 相机不需要，但保留以防万一）
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget ca-certificates curl \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-xinerama0 \
        libxcb-xfixes0 \
        libxkbcommon-x11-0 \
        libdbus-1-3 \
        libusb-1.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── Miniforge3（github官方，支持代理）──────────────────────────
RUN wget -q \
    https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh \
    -O /tmp/miniforge.sh \
    && bash /tmp/miniforge.sh -b -p /opt/conda \
    && rm /tmp/miniforge.sh \
    && mkdir -p /root/.config/pip

# 配置 conda / pip 使用清华镜像（无需代理）
COPY docker/condarc /opt/conda/.condarc
COPY docker/pip.conf /root/.config/pip/pip.conf

# 安装 mamba（使用清华 conda-forge 镜像）
RUN /opt/conda/bin/conda install -n base -c conda-forge mamba -y \
    && /opt/conda/bin/conda clean -afy

# ── conda 环境（包含 PyTorch CUDA 11.7 / TRT 8.6 / PyQt6 等）──
# ── conda 环境（仅pip装torch/torchvision，TRT相关whl用tar包）──
COPY docker/environment.yml /tmp/environment.yml
RUN /opt/conda/bin/mamba env create --channel-priority flexible -f /tmp/environment.yml \
    && /opt/conda/bin/conda clean -afy \
    && rm /tmp/environment.yml

# ── TensorRT tar包解压与whl安装（根目录）——
COPY TensorRT-8.6.0.12.Linux.x86_64-gnu.cuda-11.8.tar.gz /tmp/
RUN tar -xzf /tmp/TensorRT-8.6.0.12.Linux.x86_64-gnu.cuda-11.8.tar.gz -C /tmp/ && \
    find /tmp/TensorRT-8.6.0.12/python -name '*cp39*.whl' | xargs -I {} /opt/conda/envs/rz_radar-2026/bin/pip install {} && \
    find /tmp/TensorRT-8.6.0.12/onnx_graphsurgeon -name '*cp39*.whl' | xargs -I {} /opt/conda/envs/rz_radar-2026/bin/pip install {} && \
    find /tmp/TensorRT-8.6.0.12/graphsurgeon -name '*cp39*.whl' | xargs -I {} /opt/conda/envs/rz_radar-2026/bin/pip install {} && \
    find /tmp/TensorRT-8.6.0.12/uff -name '*cp39*.whl' | xargs -I {} /opt/conda/envs/rz_radar-2026/bin/pip install {} && \
    rm -rf /tmp/TensorRT-8.6.0.12* /tmp/TensorRT-8.6.0.12.Linux.x86_64-gnu.cuda-11.8.tar.gz

# ── 海康 MVS SDK ──────────────────────────────────────────────
# 将 docker/ 整个目录 COPY 进来，安装后删除
COPY docker/ /tmp/mvs_sdk/
RUN set -e; \
    if ls /tmp/mvs_sdk/*.deb >/dev/null 2>&1; then \
        apt-get update && \
        apt-get install -y /tmp/mvs_sdk/*.deb && \
        rm -rf /var/lib/apt/lists/*; \
    elif ls /tmp/mvs_sdk/*.tar.gz >/dev/null 2>&1; then \
        mkdir -p /tmp/mvs_unpack && \
        tar -xzf /tmp/mvs_sdk/*.tar.gz -C /tmp/mvs_unpack --strip-components=1 && \
        if [ -f /tmp/mvs_unpack/setup.sh ]; then \
            chmod +x /tmp/mvs_unpack/setup.sh && \
            bash /tmp/mvs_unpack/setup.sh; \
        else \
            find /tmp/mvs_unpack -name "*.deb" -exec apt-get install -y {} \;; \
        fi; \
    else \
        echo ""; \
        echo "╔══════════════════════════════════════════════════════╗"; \
        echo "║  ERROR: docker/ 目录下未找到 MVS SDK 安装包           ║"; \
        echo "║  请将 MVS*.deb 或 MVS*.tar.gz 放入 docker/ 目录后     ║"; \
        echo "║  重新执行 docker compose build                        ║"; \
        echo "╚══════════════════════════════════════════════════════╝"; \
        echo ""; \
        exit 1; \
    fi \
    && rm -rf /tmp/mvs_sdk /tmp/mvs_unpack

# ── 应用代码 ─────────────────────────────────────────────────
WORKDIR /workspace
COPY . .

CMD ["python", "main.py"]
