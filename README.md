# DSH Video Understanding

给 DeepSeek Harness (DSH) 及其他兼容 MCP 的模型客户端接入本地视频理解的 Windows MCP 服务。当前包版本 **0.5.3**，支持标准 stdio 传输，并提供实验性的 DSH 浏览器陪看适配器。

统一交付三种证据：**独立视觉文字 + 独立语音转写 + 带时间戳的真实关键帧图片**，由 DSH 的决策模型综合判断。视觉后端支持 VideoChat3-4B NF4 流式主动响应，保留 Qwen3-VL-4B GGUF 作为可切换后端；语音模型保持 faster-whisper small。

```text
同一视频与原始时间轴
  ├─ 无声画面 → VideoChat3 / Qwen3-VL → 动作、场景、颜色及观察文字
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

## VideoChat3 流式后端

安装主包和基础运行时后，可独立准备流式后端：

```powershell
.venv/Scripts/dsh-video-install-streaming.exe --home D:/DSH-Toolchain/video-understanding
```

需要 `uv`；该命令创建独立的 Windows Python 3.12 环境 `.venv-videochat3`，按包内 lockfile 安装官方 CUDA 13.0 PyTorch、Transformers 和 bitsandbytes，下载固定 revision 的官方 `MCG-NJU/VideoChat3-4B`。原始 BF16 权重约 8.94 GB，运行时对语言层使用 NF4，视觉编码器和投影保留 BF16。下载后验证权重 SHA-256；每次执行前验证自定义模型代码和配置 SHA-256。模型代码不从未固定的远程 main 分支动态执行。

安装默认不修改后端选择。确认推理可用后，把运行时目录的 `backend.json` 设置为 `{"backend":"videochat3"}`，或安装时加 `--activate`。切回 `{"backend":"qwen"}` 即使用旧后端，原有模型无需删除。没有此文件时默认 Qwen，兼容旧安装。

VideoChat3 默认 `stream_mode=caption`，持续用中文描述当前窗口，避免宽泛总结请求在主动协议下持续静默。默认 2 FPS，每 4 秒视频形成一轮观察，使用原生视频输入和时间压缩，附带前 2 秒画面作为上下文。各轮不回填先前生成的回答，降低错误描述自我强化的风险。若要等待某个具体事件，可传 `stream_mode=proactive`，按官方 `Silence / Standby / Response` 协议每秒观察一轮、保留最近 8 轮，必要时提高下一轮图像预算。持续描述会在一句话完成时停止生成，并设置字符和 token 上限；截断情况标记为不确定性。每轮完成后即保存结果，MCP 客户端可在整段完成前获取文字和关键帧。`stream_cursor` 是下一次获取新观察时使用的 `segment_offset`；`stream_active` 表示任务还可能产生新结果。即使本次没有新片段，也应保留该 cursor 等待后续结果。

这是连续输入有序帧、带有限历史的模型流式观察。为兼容已修复安全公告的 Transformers 5.10.4，显式恢复上游 checkpoint 的输出层权重绑定，并适配新版生成输入和视频预处理接口；预处理保留固定模型的归一化、分块及时间戳逻辑。视觉 SDPA 按原有注意力分区逐块执行，避免构造整个窗口的巨大块对角掩码；CPU FP32 与 GPU BF16 数值对照检查验证其等价性。官方示例会重新处理滑动窗口，并不自动复用所有历史视觉缓存；本适配器也不宣称无限视频记忆或必然实时。超过窗口的内容依靠已保存的观察文字供决策模型回顾。`Silence/Standby` 不是“画面没有事件”的证明，未带正确状态标签的输出会明确标记不确定性。流式观察的时间表示输入窗口，不能当作精确动作起止时间。

这五个 MCP 工具的输入仍是本地视频文件或先下载的公开 URL。输出通过 MCP 轮询增量读取，不是要求客户端解析额外 SSE 协议。ASR 仍独立处理指定范围，可能比第一轮视觉结果晚到；检查通道状态后再作完整判断。浏览器当前播放器采集由下面的独立适配器提供。

## 浏览器陪看（0.5.0，实验性）

在 DSH 浏览器助手里说“陪我看这个视频”，通过 `browser_watch_video` 启动当前受控页面的 HTML5 播放器观察；说“停止陪看”结束。综合模式的 video 工具组及浏览器会话可使用该工具。它不会替用户播放或拖动视频。

适配器每次采集约两秒画面和音频，独立产生视觉文字、语音文字及三张真实 JPEG，再交给当前会话配置的图像模型决定是否接话。沿用当前人设，通常安静观察，偶尔自然说一句；内部决策 JSON 不展示给用户。暂停、拖动、换源会使旧回复失效，页面变化结束陪看；仅保留最新待处理窗口，避免落后后逐段补播。启动时自动加载 VideoChat3，陪看期间保持模型，停止后清理自有进程树。

它需要额外安装源代码适配器，**仅更新 MCP 包不够**。目前适配已安装的 DSH 0.2.1.0、bridge-browser 0.0.7 和浏览器扩展 0.1.4 源码；未知源码版本会拒绝自动修改。安装、权限、测试范围见 [browser-adapter/README.md](browser-adapter/README.md)。

这台机器实测模型冷启动约 30 秒，预热后的四秒合成窗口完整处理约 2.75 秒；并非播放发生后立刻回应。当前只支持 1 倍速、单次最多 30 分钟，需要可采集的 HTML5 视频及支持图片输入的决策路由。真实浏览器录制与 DSH 持续回复已分别验证；真实 B 站首次侧栏测试在启动状态检查失败，尚未验证陪看成功。页面存在普通 video 元素，不能据此误报为封装组件或 DRM 限制。0.5.1 增加适配协议检查，区分状态字段缺失和媒体源尚未就绪，并要求失败时停止重复尝试，不自动改成整段分析。

后续真实页面已成功采集并完成模型加载，但候选回复进入会话后输出为空，被时效/播放状态保护取消。0.5.2 优化回复交接：仅在 250 毫秒内复用刚完成的播放检查，超过该时间重新读取；仍拒绝超过八秒、暂停或跳转后的旧证据。只有实际发布才开始接话冷却，丢弃的回复不再消耗冷却时间。`browser_watch_video(action=status)` 与运行时 `watch/<id>/status.json` 可检查观察、决策、排队、发布和拒绝原因。新一轮真实模型回归发布成功；真实侧栏仍需使用新构建复测。

0.5.3 根据下一次真实页面失败修正时间预算：八秒内的新观察才进入决策，决策最多八秒，最终接话的证据年龄最多十六秒（播放器与实际墙钟均检查）；仍受暂停、跳转、换源和用户输入限制。首次有可辨证据时尝试一句自然观察，之后保持克制。视频结束会停止并释放模型，暂停只在状态变化时清空旧结果；累计丢弃原因和最后一次决策不被后续轮询覆盖。已用真实网页录制片段、实际 GPU/ASR 与 DSH 路由验证约 8.5 秒证据年龄的接话和结束释放，模拟浏览器传输下通过；真实侧栏复测仍待完成。

## 按需自动启动

无需手动打开推理程序。连接 MCP、列出工具、查询状态和读取旧结果都不会加载 GPU 模型。分析任务排到 GPU 时，自动启动所选后端；VideoChat3 在独立子进程加载权重，Qwen 启动隐藏 llama-server 并等待健康检查。完成、取消或推理失败后关闭本任务的后端，下一次任务再加载。Windows 虚拟环境启动器的整个自有子进程树会一并清理。为减少后台调度造成的延迟，推理进程临时请求 HighQoS 和定时器精度，进程退出后结束，不更改系统电源方案。

首次调用需要等待权重载入。工具立即返回任务 ID，使用 `get_video_job` 轮询进度。启动失败会返回失败信息；日志分别在任务目录的 `videochat3.log` 或 `llama.log`。`video_runtime_status.ready` 表示依赖文件存在，不表示 GPU 模型已加载或硬件一定兼容。工具调用不会自动下载大模型。

## 工具

| 工具 | 用途 |
|---|---|
| analyze_video | 提交本地视频或公开可下载的视频 URL |
| get_video_job | 一次取得两路文字、通道状态与最多 4 张真实 PNG 图片 |
| inspect_video_segment | 复看指定原视频范围 |
| cancel_video_job | 请求取消任务 |
| video_runtime_status | 检查依赖和最近任务 |

任务通过独立隐藏 Windows worker 执行，提交的 MCP 连接断开后仍可运行。GPU 任务串行，完成后卸载模型。单任务范围最多 30 分钟；复看最多 60 秒。默认 2 FPS。Qwen 视频推理最长边 448；VideoChat3 使用受限像素预算和滑动窗口，无法保证瞬间动作、小字或逐帧时间精度。

这些低分辨率预算仅用于视频模型推理。关键帧从原视频重新解码，最长边最高 1280 像素，不放大小尺寸原片；单帧 PNG 最多 2 MiB，复杂画面会缩小。选择片段首尾及最大画面变化前后，最多 4 帧。这是轻量的帧差选择器，不是语义镜头检测模型。

结果含 `evidence_bundle.visual_text`、`speech_text`、`keyframes` 与 `delivered_image_ids`。图片以 MCP `ImageContent` 返回，JSON 中只有元数据，不嵌入 base64。`segment_offset/segment_limit` 控制片段分页，`image_offset/image_limit` 控制该片段页内的图片分页，按各自的 `next_offset/next_image_offset` 继续读取；`image_limit=0` 明确只读文字。`channels` 标记视觉、语音、关键帧是否完成、缺失、禁用或失败。

旧版任务不会被伪装成三路结果，会标记 `legacy_notice`；需要重新分析才能获得独立视觉和关键帧。

**DSH 需要支持图像输入的决策模型和启用的附件功能。** 如果当前路由拒绝图片，应明确报告；不能把返回图片路径当作模型已看图。模型不支持图像时仍可取得两路文字，但不算完成三路视觉核验。

可对已有文件逐轮产生流式结果；是否跟得上播放需要在实际硬件和视频上测量，不能从模型名称推定。

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

