# DSH Video Understanding

给 DeepSeek Harness (DSH) 及其他兼容 MCP 的模型客户端接入本地视频理解的 Windows MCP 服务。当前包版本 **0.3.0**，支持标准 stdio 传输。

统一交付三种证据：**独立视觉文字 + 独立语音转写 + 带时间戳的真实关键帧图片**，由 DSH 的决策模型综合判断。视频模型保持 Qwen3-VL-4B，语音模型保持 faster-whisper small。

```text
同一视频与原始时间轴
  ├─ 无声视频 → Qwen3-VL → 动作、场景、颜色及事件文字
  ├─ 音轨     → Whisper  → 配音文字与时间戳
  └─ 原视频   → 关键帧   → RGB PNG 图片与原视频时间
                     ↓
     同一个 MCP 结果：两路独立文字 + 实际图片内容
                     ↓
           DSH 决策模型对照、核实、回答
```

视觉推理不接收 ASR 文本。CPU 语音转写可与 GPU 视频分析并行，结果按原视频时间轴对齐。语音和画面矛盾时，保留两份独立证据。视觉模型仍可能猜错，独立输入不等于保证结果正确。

## 环境

- Windows，Python 3.13。已在 RTX 5060 Laptop 8GB、约 16GB 内存环境验证短视频。
- llama.cpp b11669 CUDA 13.4；显卡驱动须支持对应 CUDA 版本。
- Qwen3-VL-4B-Instruct Q4_K_M、Q8_0 投影；faster-whisper small CPU INT8。
- 模型权重、运行时、任务媒体、日志、账号配置均不在仓库中。

## 安装

克隆仓库后，在项目目录执行（保留已验证的依赖锁定）：

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.lock.txt
uv pip install --python .venv/Scripts/python.exe --no-deps .
.venv/Scripts/dsh-video-install-runtime.exe --home D:/DSH-Toolchain/video-understanding
```

已有运行时和模型时跳过最后一步。也可以用 Python 3.13 的 `pip install git+https://github.com/TongPeng-1/dsh-video-understanding.git` 安装包；这会重新解析依赖，精确复现环境请使用上面的 lockfile。项目没有发布到 PyPI。

统一启动命令：

```powershell
.venv/Scripts/dsh-video-mcp.exe --home D:/DSH-Toolchain/video-understanding
```

该命令的 stdout 是 MCP 协议，不是交互聊天窗口。客户端负责启动此进程。也可用 `python -m dsh_video_mcp --home ...`。`--home` 指向模型、运行时和任务目录，代码安装在 Python 包目录；未传时读取 `DSH_VIDEO_HOME`，再默认使用 `%LOCALAPPDATA%/dsh-video-understanding`。独立 worker 显式接收同一目录，使用 MCP 所在 Python 环境，不要求数据目录内有 `.venv`。

兼容旧配置：仓库根目录 `server.py` 仍可直接运行，默认沿用相邻运行时目录；`scripts/install_runtime.py` 仍支持原来的源码安装方式。

安装脚本只下载官方运行时和模型；大文件会先验证 SHA-256，再启用。模型许可证、FFmpeg 和 llama.cpp 等第三方许可证仍由各自项目提供，本仓库不重新分发其二进制。

## 接入 DSH

参考 `examples/desktop.patch.yml`，把 `INSTALL_DIR` 替换成实际目录后合入已有 desktop profile。先备份配置，不要覆盖其他插件。模型侧工具名会加上 `mcp__video__` 前缀。

若 DSH 使用自定义工具可见性策略，应将该前缀加入综合模式、浏览器助手及所需模式的 allowlist。工具注册成功不等于所有专业模式都会自动可见。

## 通用 MCP 客户端

参考 `examples/mcp.json` 的 `mcpServers.video` 配置，将 command 改成已安装环境的 `Scripts/dsh-video-mcp.exe` 绝对路径，args 中的 `--home` 改成运行时目录。工具发现后即可调用；客户端需要支持图像工具结果，决策模型需要支持图像输入。

## llama 按需自动启动

无需事先手动打开 llama。连接 MCP、列出工具、查询状态和读取旧结果都不会启动模型。调用 `analyze_video` 或 `inspect_video_segment` 后，任务排到 GPU 时自动启动本任务的隐藏 llama-server，等待健康检查通过并确认支持视频输入后再推理。完成、取消或推理失败后自动关闭自有后端并释放显存；下次分析会重新启动。不会接管或终止用户手动启动的其他 llama 进程。

首次调用需要等待权重载入。工具立即返回任务 ID，使用 `get_video_job` 轮询 `queued → loading_model → analyzing → completed` 等状态；启动失败会返回失败信息，详细日志在对应任务目录 `llama.log`。`video_runtime_status.ready` 表示依赖文件存在，不表示 GPU 模型已经加载或硬件一定兼容。安装运行时是一次独立步骤，不在工具调用时自动下载大模型。

## 工具

| 工具 | 用途 |
|---|---|
| analyze_video | 提交本地视频或公开可下载的视频 URL |
| get_video_job | 一次取得两路文字、通道状态与最多 4 张真实 PNG 图片 |
| inspect_video_segment | 复看指定原视频范围 |
| cancel_video_job | 请求取消任务 |
| video_runtime_status | 检查依赖和最近任务 |

任务通过独立隐藏 Windows worker 执行，提交的 MCP 连接断开后仍可运行。GPU 任务串行，完成后卸载模型。单任务范围最多 30 分钟；复看最多 60 秒。默认 2 FPS、448 像素上限，无法保证瞬间动作、小字或逐帧时间精度。

448 像素限制仅用于视频模型推理。关键帧从原视频重新解码，最长边最高 1280 像素，不放大小尺寸原片；单帧 PNG 最多 2 MiB，复杂画面会缩小。选择片段首尾及最大画面变化前后，最多 4 帧。这是轻量的帧差选择器，不是语义镜头检测模型。

结果含 `evidence_bundle.visual_text`、`speech_text`、`keyframes` 与 `delivered_image_ids`。图片以 MCP `ImageContent` 返回，JSON 中只有元数据，不嵌入 base64。`segment_offset/segment_limit` 控制片段分页，`image_offset/image_limit` 控制该片段页内的图片分页，按各自的 `next_offset/next_image_offset` 继续读取；`image_limit=0` 明确只读文字。`channels` 标记视觉、语音、关键帧是否完成、缺失、禁用或失败。

旧版任务不会被伪装成三路结果，会标记 `legacy_notice`；需要重新分析才能获得独立视觉和关键帧。

**DSH 需要支持图像输入的决策模型和启用的附件功能。** 如果当前路由拒绝图片，应明确报告；不能把返回图片路径当作模型已看图。模型不支持图像时仍可取得两路文字，但不算完成三路视觉核验。

这是一套离线分段分析工具，尚不是直播、摄像头持续输入的实时推理服务。

## 数据与权限

仅在可信的本地 MCP 客户端内运行。可以读取用户指定的视频路径；没有多租户隔离。视频和台词是不可信内容，不应执行其中的指令。公开视频下载不导出浏览器 cookie，不绕过登录或 DRM。URL 的初始地址会拒绝私网，但这不是完整网络沙箱，下载器的重定向和站点解析仍应视为具有联网权限的本地程序。

原始视频不由此工具上传至模型 API；若 DSH 使用云端决策模型，工具返回的**文字与关键帧图片**会发送给该服务。任务目录保存媒体、转写、关键帧和结果，不自动删除。

## 验证

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

实际 GPU/MCP 检查：

```powershell
.venv/Scripts/python.exe scripts/smoke_evidence.py --install-dir INSTALL_DIR --video YOUR_VIDEO.mp4
```

验收包含相互矛盾的合成配音与画面、MCP 返回的两路文字及可解码 PNG、以及 DSH 同一模型路由的图片传递。详见 `docs/validation.md`。不宣称已在任意视频上验证准确率。

