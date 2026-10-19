# DSH 浏览器陪看适配器（实验性）

在当前 DSH 浏览器会话说“陪我看这个视频”，结束时说“停止陪看”。模型调用原生工具 `browser_watch_video`，action 为 start/status/stop，可选 frame 与 videoIndex。它独立于五个标准视频 MCP 工具，并非通用 MCP 浏览器采集接口。

## 安装

先按仓库 README 安装 0.5.0 主包、基础运行时及 VideoChat3 后端。适配器固定使用该运行时下 `.venv/Scripts/python.exe` 和 `.venv-videochat3/Scripts/python.exe`，因此主包需要装进这个 `.venv`。还需要已经安装的 DSH 浏览器源码工作区及其现有 pnpm 开发依赖；脚本不会安装依赖。

从仓库检出目录执行：

```powershell
python scripts/install_browser_adapter.py --home D:/DSH-Toolchain/video-understanding --activate
```

默认 profile 是 `%USERPROFILE%/.dsh/profiles/desktop`，workspace 是 `%USERPROFILE%/.dsh/dsh-browser`，可通过 `--profile`、`--workspace` 指定。已验证版本为 DSH 0.2.1.0、bridge-browser 0.0.7、扩展 0.1.4。补丁按已知源码锚点匹配，遇到其他版本会报错。不要直接覆盖不同版本的源码。

脚本备份被修改的源文件和配置，构建 bridge 与扩展，更新现有稳定扩展目录的 background.js/content.js，并在 profile 中指向带内容哈希的新模块。备份位于 profile/backups/video-companion-*，manifest.json 记录源文件和配置位置；扩展 bundle 另有 extension-* 备份。脚本不是事务安装器；构建失败时应先检查备份和错误再处理。

已经打开的浏览器需要重新加载现有 DSH 扩展或关闭后重开。文件复制成功不代表当前浏览器已使用新代码；应在浏览器助手中成功调用工具并取得观察结果后确认。卸载时按备份恢复配置、源码与两个扩展 bundle，再重新构建和加载；不要覆盖其他更新后才修改的配置。

## 运行约束

- 只读取当前会话受控标签页选中的 HTML5 视频。默认选最大的可见播放器，不抓无关桌面、不导出 cookie、不绕过 DRM；不自动播放、拖动或控制其他页面。
- 沿用扩展现有共享和审批规则。在 ask 模式中首次批准一次本次陪看，授权绑定会话、随机 watch ID、标签页和精确 document，30 分钟到期，停止时释放。页面改变后不把授权转移到新页面。现有 unrestrictedAccess 仍遵循原扩展语义。
- 每次录制约两秒，最多 4 MiB；窗口队列只保留最新一项。两路文字独立，三张 JPEG 来自真实采集片段，最长边最多 1280 像素。决策模型必须声明支持图片输入。
- 同一时刻使用串行 GPU 锁。陪看保持 GPU 模型，其他视频任务可能等到停止陪看后才能运行；暂停时仍保持模型以便恢复。
- 决策间隔至少八秒，主动接话间隔至少二十秒；用户输入优先。暂停、结束、拖动使过时回复失效；换源、换页面、非 1 倍速结束陪看。模型只能讨论实际采集的窗口，跳过的内容不能声称看过。
- 语音短窗口可能截断句子，无转写不代表无声。小字、快速动作和身份识别仍可能出错。云端决策路由会收到文字和关键帧；原视频片段在本地处理。处理中片段会清理，停止异常时可能留下最后一个片段、日志或请求文件，均在运行时 watch 子目录内。

## 已测与待测

已验证真实浏览器 VP8/Opus 片段、暂停拒绝及拖动失效；实际 GPU 常驻处理多窗口、独立语音与三张可解码图片；实际 DSH 路由的图片决策和原生对话接话。持续控制器集成测试使用模拟浏览器传输注入实际录制片段，并非 B 站全链路测试。

真实 B 站页面的最终侧栏联调待完成：本轮 Edge 可列出视频标签页，但控制连接无法附加调试器，未能提交陪看指令并观察结果。不能将文件部署或上述分项通过等同于已验证所有站点。详细测量见 [验证记录](../docs/validation.md)。
