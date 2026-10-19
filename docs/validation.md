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

These checks establish the pipeline and one model route, not general video accuracy. Other DSH model routes can refuse images. Video event localization remains approximate; the lightweight frame-difference selector can miss semantically important but visually subtle moments. No live-camera/streaming backend or model replacement was added. Long videos and all supported video websites were not exhaustively tested.

The installer code was reviewed and Python-compiled; the existing verified runtime was reused for this upgrade instead of downloading every model again. The current FFmpeg release URL is mutable; if upstream changes it, the installer will fail its pinned hash check rather than silently trust different bytes.
