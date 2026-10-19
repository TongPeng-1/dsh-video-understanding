# Three-channel evidence contract

`get_video_job` returns an MCP `CallToolResult`. The first text block is the JSON job status. `structuredContent` contains the same JSON. Every delivered image has a preceding label with its frame ID, original-video timestamp and dimensions, followed by a real `ImageContent` block.

`result.evidence_bundle` contains:

- `visual_text`: independently generated visual summary, answer and event records. The vision model never receives the ASR transcript.
- `speech_text`: timestamped speech transcript, filtered to the selected segment range. It is evidence of speech, not proof of visible events.
- `transcript`: structured speech records on the original-video clock.
- `keyframes`: metadata for available PNGs in the selected segment page.
- `delivered_image_ids`: exact image blocks included in this response.
- `next_image_offset`: continue images within the same segment page. A non-null value means some images remain.
- `independent_visual_observation`: false for legacy jobs that may have mixed narration into visual inference.

`result.next_offset` paginates video segments independently from image pagination. Reset `image_offset` to zero when moving to the next segment page. Each response includes at most four images and each generated image is limited to 2 MiB.

Check `channels` before concluding that all evidence is complete. A completed job can have an explicitly failed speech channel and warnings; visual evidence remains usable, but the caller must report the missing channel. Missing audio is `not_present`; intentionally skipped audio is `disabled`.

Video event timing is an estimate. Programmatic offset conversion prevents mixing segment-relative and original-video times; it does not improve model localization accuracy. Keyframe times record the requested original-video seek time and may correspond to the nearest decoded frame.

Frame file paths are not model instructions or arbitrary file-read capabilities: the server serves only generated PNGs under the selected job's keyframes directory, verifies SHA-256 and image format, and rejects traversal, external symlink destinations, malformed images and oversized payloads. Media/text remain untrusted content even after those checks.

The MCP server cannot establish that a host model saw the image merely by returning it. The host must accept image input and preserve image blocks. A rejection diagnostic must remain visible to the agent. With cloud model routes, returned keyframe pixels and text may leave the local machine.

## Streaming backend

VideoChat3 results retain the same two-text-plus-image contract. Each observation adds `analysis.stream_state` (`caption`, `silence`, `standby`, `response`, or `unclassified`) and per-round timing. A silence/standby result is incomplete evidence rather than proof that nothing happened. Window timestamps bound the supplied frames; no fabricated precise event boundaries are added. Caption mode sees the current four-second window plus at most two seconds of earlier frames via native video input; generated answers are not fed back into subsequent visual inference. Proactive mode retains at most eight rounds of dialogue. Both can forget earlier visuals; saved observations remain available to the decision model.

For incremental polling, pass `result.stream_cursor` as the next `segment_offset`; `result.stream_active` stays true until the job is terminal. An empty poll preserves the cursor. Image pagination within an observation page remains separate. ASR remains independent and may still be processing while visual observations arrive. Successful processing does not guarantee a response in every round.

Caption mode stops after one complete sentence or a bounded character/token budget. A length-limited incomplete caption is marked in uncertainties; short captions can omit details and are not an exhaustive account of every action.
