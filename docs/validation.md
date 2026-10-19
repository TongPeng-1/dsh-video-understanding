# Validation record — 2026-10-19

The published baseline is commit `6cf2001026efbb2e0a546c2316b18104eef04781`. The evidence upgrade retains Qwen3-VL-4B Q4_K_M, its Q8_0 projector, Whisper small CPU INT8 and llama.cpp b11669 CUDA 13.4. The Qwen weight/projector hashes remain unchanged.

## Checks performed

- 14 standard-library unit tests: input validation, independent visual inference API, original-time offset conversion, two independent text channels, real PNG contents, image pagination, omitted images, legacy results, explicit ASR failure, frame-change selection, path traversal rejection, corrupted-image rejection and invalid-image rejection.
- Python compilation and dependency compatibility check in the existing Windows environment.
- MCP handshake, discovery and actual calls, not only direct Python invocation.
- Real GPU analysis of an 8-second synthetic video: a red square moves right before a blue circle appears. An intentionally false narration says the circle appears first and the square never moves. Visual inference correctly retains motion and sequence while the ASR text independently preserves the contradictory narration.
- The actual MCP response contains visual text, speech text and four valid PNG image content blocks. Generated image bytes are checked with Pillow; JSON structured content contains metadata rather than base64.
- The submitting MCP connection is closed before result polling from a fresh connection. The independent Windows worker still completes.
- Actual DSH headless runtime using the same configured `workbuddy / deepseek-v4.1-flash` route and its attachment subsystem. An image-only MCP probe returns an unlabeled color/shape fixture; DSH correctly reports a red square, blue circle and green triangle.
- A second isolated DSH session calls the real video tool and receives the complete evidence bundle. Its final answer identifies the narration/visual contradiction, compares first and last image positions, and distinguishes visible motion from transcribed claims.
- The desktop's existing video MCP connection is refreshed through its reconnect mechanism. Mode tool names/prefixes remain unchanged; existing visibility policy continues to apply.

The isolated sessions do not message or modify the user's existing DSH chats. Their raw traces, media, provider configuration and local paths are not published.

## Limits

These checks establish the pipeline and one model route, not general video accuracy. Other DSH model routes can refuse images. Video event localization remains approximate; the lightweight frame-difference selector can miss semantically important but visually subtle moments. The baseline did not add a live-camera/streaming backend or model replacement; the 0.4.0 checks below supersede this for file-based incremental inference. Long videos and all supported video websites were not exhaustively tested.

The installer code was reviewed and Python-compiled; the existing verified runtime was reused for this upgrade instead of downloading every model again. The current FFmpeg release URL is mutable; if upstream changes it, the installer will fail its pinned hash check rather than silently trust different bytes.

## MCP package 0.3.0

- Built a wheel and installed it into the existing Windows Python environment. Console help and dependency compatibility check pass (54 installed packages).
- 17 unit tests pass, including explicit runtime-home propagation to detached workers, readiness polling and cleanup on failed model startup.
- Started with zero llama-server processes, connected through the installed `dsh-video-mcp.exe`, discovered all five tools, and submitted an 8-second local video. The job automatically started llama and completed after the submitting MCP connection closed. Returned independent visual/speech text and four decoded PNG images. Local integration job: `1e5c8c70eb804d23858fdd02ab07f724` (media/results not published).
- After completion, verified zero llama-server processes. A fresh installed-package MCP handshake, tool discovery and runtime-status call kept the process count at zero. The imported module location was confirmed under the installed environment's site-packages.
- Updated DSH's existing video entry to the standard console command with an explicit runtime directory; existing tool prefix and mode rules are retained.

This packaging test used the current verified runtime instead of downloading models again. Cold-start operation, normal completion cleanup and startup failure handling are checked; arbitrary process termination, all GPU/driver combinations and repeated-job concurrency stress are not exhaustively tested.


## VideoChat3 0.4.0

Test hardware: Windows, RTX 5060 Laptop 8 GB, 16 GB RAM. The visual model is the pinned official VideoChat3-4B checkpoint with NF4 language weights. CPU Whisper small remains independent. The main MCP environment and isolated GPU environment use Python 3.13 and 3.12 respectively.

- 30 unit tests pass; Python compilation, wheel build, dependency compatibility and diff whitespace checks pass. The GPU environment contains 46 packages; pip-audit reported no known vulnerabilities after updating the initial vulnerable dependencies. This does not establish codec safety or general model accuracy.
- Actual CUDA/NF4 execution passes. Partitioned attention matches the original block-diagonal calculation in CPU FP32 and GPU BF16 checks.
- Caption mode uses four-second native-video windows plus two seconds of prior frames, preserving original timestamps. Previous generated answers are not fed back into the visual model. This fixes the sustained repeated-answer behavior found in the first streaming implementation. Compatibility preserves upstream normalization and video patch layout under Transformers 5.10.4.
- A silent eight-second synthetic video shows a red square moving from left to right, followed by a blue circle. A direct runner test with a motion-focused question identifies this motion and order. The installed MCP smoke test identifies the color/shape order but omits the motion in its short caption, while transcribing the deliberately contradictory narration independently. It returns both text channels and four verified PNG blocks after closing the submitting connection.

### Same-source full-pipeline timing

| Measurement | Result |
|---|---:|
| Source duration (720p) | 214.785 s |
| Previous Qwen full job, including ASR | 309.421 s |
| VideoChat3 full job, including ASR/keyframes and MCP polling | 141.223 s |
| First observation received, cold start | 28.536 s |
| Model/import startup within new job | 19.844 s |
| Completed observation windows | 54 |
| Wall time / video duration | 0.658 |

This single run is about 2.19 times faster than the prior job and finishes before the video's playback duration. It does not establish synchronized live playback or a universal throughput guarantee. Startup still delays the first observation. ASR and visual channels can complete at different times. The final packaging changes only generalize the same two-second look-back to other supported sampling rates and mark token-limited captions as incomplete; the full timing run used 2 FPS.

Visual spot checks compare the original frames against observations of eating, character/scene changes, computer use, and a bicycle illustration appearing later on screen. The later windows continue to react to new frames. Some captions remain generic, miss gestures, or misread names and small text. A short caption per window is not an exhaustive action log; returned keyframes remain necessary for decision-model review. No formal accuracy score or broad multi-video benchmark is claimed. User media, filenames, transcripts, private configuration and raw traces are not published.

- Actual MCP cancellation test passes: the requested job becomes cancelled, its launcher and backend Python descendants are gone, and the same MCP connection remains usable. A separate real process-tree fixture covers cancellation after descendants are already running.

## Browser companion 0.5.0

This is an experimental browser-source adapter, not a claim of production compatibility with every site. Tested on the same Windows/GPU installation, with DSH 0.2.1.0, bridge-browser 0.0.7 and browser extension 0.1.4.

- 31 Python unit tests pass. Bridge typecheck/build and 15 selected bridge tests pass; extension typecheck/build and 46 selected tests across six files pass. These cover decision parsing, stale evidence, native text streaming, capture validation, existing browser dispatch, consent-once behavior, document changes, sharing-off behavior and owner isolation. No new dependency was added.
- Actual Edge and in-app browser recording of an owned synthetic HTML5 player produces a two-second WebM containing VP8 video and Opus audio. Pause refusal and seek invalidation pass. Testing found and fixed base64 extraction from codec-bearing Data URLs (the MIME codec list itself contains a comma).
- Actual resident VideoChat3 plus independent CPU Whisper processes two consecutive four-second synthetic windows without reloading. Cold ready: 30.34 s; first window: 6.484 s; next window: 2.745 s, including ASR. Each returns three valid JPEGs. Stop releases the owned process tree. Initial native-module import on a Python 3.13 pool thread hung on Windows; importing faster-whisper on the main thread before worker startup resolves the reproduced hang.
- Actual configured DSH image-capable route and attachment subsystem accept both text channels and three real JPEGs. One decision took 2.306 s and identified the moving red square versus contradictory narration. Internal decision JSON stays inside the controller.
- Continuous controller integration uses the real resident backend, ASR, attachments, auxiliary decision and native DSH agent, with a simulated controlled-browser transport feeding actual recorded WebM. A simulated 12-second seek increments the epoch. Two runs produce a natural reply and close cleanly. The later run captures 12 windows, makes one decision and publishes the already generated reply in the native conversation 61 ms after queuing it: “红方块这慢悠悠地挪窝，看着还挺悠闲的。” The 61 ms measures publication only, excluding recording, inference, cold start and decision latency; it is not end-to-end reaction time.
- Real DSH offline-video style tests read actual returned images and identify motion/audio contradiction. Updated guidance keeps the current persona and ordinary concise prose, distinguishes missing evidence, and avoids narrating internal model/ASR/attachment steps. This is observed behavior on the tested route, not a guarantee for all prompts/models.
- Installed wheel is 0.5.0; the backed-up installer builds both installed source projects and updates existing profile module URLs and extension bundles. This establishes deployed files, not live browser registration.

### Outstanding live-page check

The user reopened Edge on a real Bilibili video with the DSH browser assistant. Browser inventory detects the expected video tab, but attempts to attach/read it time out and then report an unattached debugger. No instruction was submitted to the real side panel in that state. Full Bilibili → installed extension → desktop companion → visible side-panel response, including actual page pause/seek behavior, remains unverified. The fixture and simulated-transport tests above must not be presented as that end-to-end test. No broader accuracy or zero-delay guarantee is claimed. Private recordings, runtime paths/configuration and raw traces are excluded from publication.

## Live-page failure and diagnostics 0.5.1

The user subsequently submitted the companion instruction. Local session tool records confirm that browser_watch_video was registered and called, but failed at startup with “No accessible HTML5 video in the selected frame.” No resident worker was launched in those empty watch directories. Trying videoIndex 1 produced “No selected HTML5 video”, whereas index 0 reached the host state/source check. DSH then silently chose full-file MCP analysis. That fallback completed processing 22 windows of an approximately 86-second public video; it is not synchronized companion success, and completion alone does not establish that the decision model read every evidence page.

After the browser connection recovered, read-only inspection of the actual page found one ordinary light-DOM VIDEO under the player wrapper, a valid blob currentSrc and 1280×714 decoded dimensions. Therefore the assistant's explanation that an encapsulated component prevented access was unsupported. The original host message conflated a missing videoState response and an empty source. The exact active-bundle/transport failure remains unresolved until a reload test; no shadow-root or DRM workaround was added.

0.5.1 adds an explicit private adapter marker plus state validation and different errors for missing protocol fields and a source that is not ready. A regression test sends raw state/clip fields through the actual background dispatcher, ensuring the text wrapper does not discard them. Guidance and tool description now prohibit unchanged repeated starts, unsupported player-cause guesses and silently substituting full-video analysis for a live companion request. Startup is acknowledged only after tool success.

Bridge typecheck and 16 selected tests pass; extension typecheck and nine video-specific tests pass. Both production builds and the 0.5.1 wheel build pass. No model/inference logic or dependency changed in this follow-up. Updated files are deployed with backups. Reloading the actual extension is required; browser security policy blocks automation of its internal extension-management page, so that step was handed to the user. Live startup/capture/reaction/pause/seek success remains pending and is not represented as fixed by diagnostic tests.
