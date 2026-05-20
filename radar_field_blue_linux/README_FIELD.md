# Blue Radar Field Package

这个文件夹是蓝方赛场接收和解析用的最小包。Linux 上直接在本文件夹内运行。

## 运行顺序

终端 1：

```bash
python3 radio.py
```

终端 2：

```bash
python3 field_parse.py
```

也可以运行：

```bash
chmod +x *.sh
./run_radio.sh
./run_parser.sh
```

## 输出含义

`field_parse.py` 同时监听四个 UDP：

```text
INFO -> 55557
L1   -> 55558
L2   -> 55559
L3   -> 55560
```

关键输出：

```text
INFO ...          信息波解析结果
INFO_OK ...       信息波一轮 0x0A01~0x0A05 解析完成
PARSE_OK ...      某一级干扰波 CRC 通过并解析到密钥
DECODED_LEVEL ... 当前最高已解析到的干扰等级
UPLOAD_READY ...  严格按 1 -> 2 -> 3 顺序给出的待上传密钥
```

对接上传时只认 `UPLOAD_READY`，不要直接用 `PARSE_OK` 或 `DECODED_LEVEL`。

## 当前蓝方频率

```text
RX center = 434.520 MHz
INFO      = 433.920 MHz
JAM1      = 434.920 MHz
JAM2      = 434.620 MHz
JAM3      = 434.320 MHz
sample rate = 2 MS/s
```

`radio.py` 默认配置是 RX1 接信息波、RX2 接干扰波：

```text
RX1 -> information
RX2 -> jam1/jam2/jam3
```

## Linux 依赖

需要系统里已经装好：

```text
GNU Radio 3.10
gr-iio / gnuradio.iio
libiio
PyQt5
numpy
Pluto/AntSDR 能通过 ip:192.168.1.10 访问
```

快速检查：

```bash
./check_env.sh
```

如果 `radio.py` 能打开窗口但没有 UDP 输出，优先检查：

```text
Pluto IP 是否是 192.168.1.10
RX1/RX2 接线是否和上面一致
中心频率是否还是 434.520 MHz
干扰波是否真的进了 RX2
```

## 文件说明

```text
radio.py                  GNU Radio 四波接收流程图生成的 Python 文件
radio.grc                 GNU Radio Companion 原流程图，方便 Linux 端重新打开/生成
field_parse.py            赛场总解析器，信息波 + 三级干扰波一起解析
radar_protocol.py         空中帧、串口帧、CRC 和业务数据解析
gr_air_frame_extractor.py GNU Radio 自定义帧提取块
radio_epy_block_*.py      radio.py 用到的嵌入式 Python 块入口
RM_serial_py/ser_api.py   CRC8/CRC16 实现
tools/data_parse.py       单路调试解析工具
tools/udp_airframe_probe.py UDP 端口快速探测工具
```

## 调试命令

只看信息波端口：

```bash
python3 tools/data_parse.py --wave info --port 55557
```

只看某个干扰端口：

```bash
python3 tools/udp_airframe_probe.py --wave jam --port 55558 --seconds 5
python3 tools/udp_airframe_probe.py --wave jam --port 55559 --seconds 5
python3 tools/udp_airframe_probe.py --wave jam --port 55560 --seconds 5
```

注意：同一个 UDP 端口同一时间只能被一个解析程序绑定。运行 `field_parse.py` 时，不要同时运行这些单路调试工具监听同一端口。
