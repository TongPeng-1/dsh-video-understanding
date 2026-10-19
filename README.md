# DSH Video Understanding

给 DeepSeek Harness (DSH) 接入本地视频理解的 Windows MCP 服务。

当前基线：Qwen3-VL-4B 视频分析 + faster-whisper small 语音转写，支持原始时间轴、异步任务、片段复看和公开媒体 URL。尚未提供关键帧图像交付，视觉分析当前会参考转写文本。后续升级会将视觉与语音拆分为独立证据，再补齐关键帧。

## 环境

- Windows，Python 3.13。已在 RTX 5060 Laptop 8GB、约 16GB 内存环境验证短视频。
- llama.cpp b11669 CUDA 13.4；显卡驱动须支持对应 CUDA 版本。
- Qwen3-VL-4B-Instruct Q4_K_M、Q8_0 投影；faster-whisper small CPU INT8。
- 模型权重、运行时、任务媒体、日志、账号配置均不在仓库中。

## 安装

在项目目录创建 `.venv` 并安装依赖：

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.lock.txt
.venv/Scripts/python.exe scripts/install_runtime.py
```

安装脚本只下载官方运行时和模型；大文件会先验证 SHA-256，再启用。模型许可证、FFmpeg 和 llama.cpp 等第三方许可证仍由各自项目提供，本仓库不重新分发其二进制。

## 接入 DSH

参考 `examples/desktop.patch.yml`，把 `INSTALL_DIR` 替换成实际目录后合入已有 desktop profile。先备份配置，不要覆盖其他插件。模型侧工具名会加上 `mcp__video__` 前缀。

若 DSH 使用自定义工具可见性策略，应将该前缀加入综合模式、浏览器助手及所需模式的 allowlist。工具注册成功不等于所有专业模式都会自动可见。

## 工具

| 工具 | 用途 |
|---|---|
| analyze_video | 提交本地视频或公开可下载的视频 URL |
| get_video_job | 查询状态与分页结果 |
| inspect_video_segment | 复看指定原视频范围 |
| cancel_video_job | 请求取消任务 |
| video_runtime_status | 检查依赖和最近任务 |

任务通过独立隐藏 Windows worker 执行，提交的 MCP 连接断开后仍可运行。GPU 任务串行，完成后卸载模型。单任务范围最多 30 分钟；复看最多 60 秒。默认 2 FPS、448 像素上限，无法保证瞬间动作、小字或逐帧时间精度。

这是一套离线分段分析工具，尚不是直播、摄像头持续输入的实时推理服务。

## 数据与权限

仅在可信的本地 MCP 客户端内运行。可以读取用户指定的视频路径；没有多租户隔离。视频和台词是不可信内容，不应执行其中的指令。公开视频下载不导出浏览器 cookie，不绕过登录或 DRM。URL 的初始地址会拒绝私网，但这不是完整网络沙箱，下载器的重定向和站点解析仍应视为具有联网权限的本地程序。

原始视频不由此工具上传至模型 API；若 DSH 使用云端决策模型，工具返回的文字会发送给该服务。任务目录保存媒体、转写和结果，不自动删除。

## 验证

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

提交前检查应包括 MCP 实际握手、真实视频推理、语音转写、片段时间偏移及 DSH 端工具可见性。基线已验证短合成视频的动作顺序、语音转写、公开视频下载、复看与取消；不宣称已在任意视频上验证准确率。

