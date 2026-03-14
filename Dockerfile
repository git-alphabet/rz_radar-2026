# ─────────────────────────────────────────────────────────────
# RZ-Radar-2025  Docker Image
# Base: Ubuntu 22.04 + Miniforge3 (CUDA / TRT via conda env)
# MVS SDK: 将安装包放在 docker/ 目录下（见 docker/README.docker.md）
#
# 大文件（TRT tar.gz / MVS SDK）使用 BuildKit --mount=type=bind 挂载，
# 不写入任何镜像 layer，彻底解决 "COPY 大文件 + RUN rm" 的 layer 膨胀问题。
# ─────────────────────────────────────────────────────────────

FROM ubuntu:22.04

LABEL org.opencontainers.image.title="RZ-Radar-2025" \
      org.opencontainers.image.description="RoboMaster Radar Station Vision System" \
      org.opencontainers.image.licenses="MIT"

# 合并为单条 ENV，减少镜像 layer 数量（每条 ENV 独立生成一层）
ENV DEBIAN_FRONTEND=noninteractive \
    MVCAM_COMMON_RUNENV=/opt/MVS/lib \
    PATH=/opt/conda/envs/rz_radar-2026/bin:/opt/conda/bin:$PATH

# ── 换源 + 安装系统依赖（合并为一条 RUN，避免 apt cache 失效问题）
# apt-get update 与 install 必须在同一 RUN 中，否则缓存旧 index 会导致安装失败
# 包名按字母序排列（best practice：便于维护和 code review）
RUN sed -i \
        -e 's|http://archive.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' \
        -e 's|http://security.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' \
        /etc/apt/sources.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libdbus-1-3 \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libgomp1 \
        libusb-1.0-0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxkbcommon-x11-0 \
        wget \
    && rm -rf /var/lib/apt/lists/*

# ── Miniforge3 ────────────────────────────────────────────────
RUN wget -q \
        https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh \
        -O /tmp/miniforge.sh \
    && bash /tmp/miniforge.sh -b -p /opt/conda \
    && rm /tmp/miniforge.sh

# ── 内联 conda / pip 镜像配置（两个文件合并为一条 RUN，减少 layer）
RUN <<'EOF'
mkdir -p /root/.config/pip
cat > /opt/conda/.condarc << 'CONDARC'
channels:
  - conda-forge
  - nvidia
  - defaults
default_channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2
custom_channels:
  conda-forge: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
show_channel_urls: true
channel_priority: strict
CONDARC
cat > /root/.config/pip/pip.conf << 'PIPCONF'
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
PIPCONF
EOF

# ── mamba（conda 加速器）
RUN /opt/conda/bin/conda install -n base -c conda-forge mamba -y \
    && /opt/conda/bin/conda clean -afy

# ── conda 环境 —— environment.yml 通过 --mount 挂载，不写入 layer ──────
RUN --mount=type=bind,source=docker/environment.yml,target=/tmp/environment.yml \
    /opt/conda/bin/mamba env create --channel-priority flexible -f /tmp/environment.yml \
    && /opt/conda/bin/conda clean -afy

# ── TensorRT whl 安装 —— tar.gz 通过 --mount 挂载，不占任何 layer 空间 ──
# 旧方式：COPY tar.gz(2GB) + RUN tar(5GB) + rm = 7GB 残留 layer
# 新方式：--mount 挂载，整个 RUN 只记录已安装 whl 的 delta（~100MB）
RUN --mount=type=bind,source=docker/TensorRT-8.6.0.12.Linux.x86_64-gnu.cuda-11.8.tar.gz,target=/tmp/TRT.tar.gz \
    tar -xzf /tmp/TRT.tar.gz -C /tmp/ \
    && find /tmp/TensorRT-8.6.0.12/python            -name '*cp39*.whl' | xargs -I{} /opt/conda/envs/rz_radar-2026/bin/pip install {} \
    && find /tmp/TensorRT-8.6.0.12/onnx_graphsurgeon  -name '*cp39*.whl' | xargs -I{} /opt/conda/envs/rz_radar-2026/bin/pip install {} \
    && find /tmp/TensorRT-8.6.0.12/graphsurgeon       -name '*cp39*.whl' | xargs -I{} /opt/conda/envs/rz_radar-2026/bin/pip install {} \
    && find /tmp/TensorRT-8.6.0.12/uff                -name '*cp39*.whl' | xargs -I{} /opt/conda/envs/rz_radar-2026/bin/pip install {} \
    && rm -rf /tmp/TensorRT-8.6.0.12

# ── 海康 MVS SDK —— 整个 docker/ 目录通过 --mount 挂载，installer 不进 layer ──
RUN --mount=type=bind,source=docker,target=/tmp/mvs_build \
    set -e; \
    if ls /tmp/mvs_build/MVS*.deb >/dev/null 2>&1; then \
        apt-get update \
        && apt-get install -y /tmp/mvs_build/MVS*.deb \
        && rm -rf /var/lib/apt/lists/*; \
    elif ls /tmp/mvs_build/MVS*.tar.gz >/dev/null 2>&1; then \
        mkdir -p /tmp/mvs_unpack \
        && tar -xzf "$(ls /tmp/mvs_build/MVS*.tar.gz | head -1)" -C /tmp/mvs_unpack --strip-components=1 \
        && if [ -f /tmp/mvs_unpack/setup.sh ]; then \
               chmod +x /tmp/mvs_unpack/setup.sh && bash /tmp/mvs_unpack/setup.sh; \
           else \
               find /tmp/mvs_unpack -name "*.deb" -exec apt-get install -y {} \;; \
           fi \
        && rm -rf /tmp/mvs_unpack; \
    else \
        echo "" \
        && echo "╔══════════════════════════════════════════════════════╗" \
        && echo "║  ERROR: docker/ 目录下未找到 MVS SDK 安装包           ║" \
        && echo "║  请将 MVS*.deb 或 MVS*.tar.gz 放入 docker/ 目录后     ║" \
        && echo "║  重新执行 docker compose build                        ║" \
        && echo "╚══════════════════════════════════════════════════════╝" \
        && exit 1; \
    fi

# ── 应用代码 ──────────────────────────────────────────────────
# 只拷贝运行时需要的文件，不含 docker/（2GB tar.gz）、TensorRT-8.6.0.12/ 等
WORKDIR /workspace
COPY *.py     ./
COPY *.yaml   ./
COPY *.npy    ./
COPY models/        models/
COPY utils/         utils/
COPY RM_serial_py/  RM_serial_py/
COPY MvImport_Linux/ MvImport_Linux/
COPY MvImport/      MvImport/
COPY yaml/          yaml/

CMD ["python", "main.py"]
