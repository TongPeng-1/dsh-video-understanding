# Differential review — independent evidence and keyframes

Date: 2026-10-19. Baseline: `6cf2001026efbb2e0a546c2316b18104eef04781`.

## Executive summary

| New confirmed findings | Count |
|---|---:|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

Change risk: **medium**, because generated image bytes cross a new MCP output boundary. Recommendation: **approve for the documented trusted-local-client deployment**, subject to the limits below. This is a scoped review, not a vulnerability scan or a general security certification.

## Changes and history

The baseline's `infer` accepted ASR text and put it in the vision prompt. Git blame identifies that behavior in the preserved baseline. The upgrade removes that input and the model-generated speech-evidence field, runs CPU transcription independently, and explicitly aligns its output with visual events. No authorization, URL validation or model-runtime authentication checks were removed.

New code extracts keyframes from the original video, bounds their dimensions and size, and returns PNG blocks with timestamp labels. The JSON result contains separate text channels and frame metadata. Legacy results are explicitly not claimed to be independent. DSH mode prefixes remain unchanged.

Reviewed files: full server diff, tests, smoke harness, guidance example, README, evidence contract and validation record. The baseline installer and lockfile were inspected as context; runtime/model dependencies were not changed in this upgrade. No account configuration, model weights, original media, raw traces or task result files are published.

## Trust boundaries and blast radius

Production call sites in the server (tests excluded):

| Function / boundary | Direct production callers | Validation |
|---|---:|---|
| `job_path` | 4 | Restricted ID and resolved path under job storage |
| `infer` | 1 (`worker`) | Receives silent video, question and times; no ASR parameter |
| `extract_keyframes` | 1 (`worker`) | Program-selected times, generated names and bounded PNGs |
| `read_frame` | 1 (`get_job_result`) | Job-local resolved path, PNG extension/type, dimensions, 2 MiB and SHA-256 |
| `evidence_bundle` | 1 (`get_job_result`) | Separately tagged text channels and legacy flag |
| `get_job_result` | 1 (MCP wrapper) | Pagination bounds and at most 4 images per response |
| `transcribe_audio` | 1 worker submission | Separate CPU worker; failure retained as a failed channel |

Media and ASR remain untrusted content. No media-derived string is used as executable code, shell command text or an image output filename. Subprocess argument arrays are preserved. Inference binds to loopback with a per-launch random key.

## Adversarial checks

- A manifest path such as `../outside.png` cannot turn image retrieval into an arbitrary file read; resolution must remain in the selected job's keyframes directory. External symlink destinations also fail the containment checks.
- A modified generated file fails SHA-256 before image delivery. A non-PNG renamed to PNG fails decoding/type checks. Oversized files are refused before reading their contents.
- Frame and segment pagination have separate cursors, so omitted images are visible rather than silently described as inspected.
- Old ASR-conditioned job results carry a legacy warning and an independent-visual flag of false.
- ASR failure does not overwrite visual evidence or appear as a completed speech channel.
- A cloud decision model receives returned keyframe pixels as well as text. This expanded payload is stated in the tool instructions, README and evidence contract; no claim of an entirely offline end-to-end system is made.

## Verification

14 unit tests pass. Real GPU/MCP tests return independent text channels and valid PNG content. An intentionally contradictory narration remains distinct from observed motion. DSH's actual installed runtime and the current model route accepted an image-only probe and the complete three-channel response. The same model route identified the contradiction and compared actual first/last frame positions. A 1280×720 source produced 1280×720 keyframes, independently of the 448-pixel video-inference preprocessing.

## Coverage limits and residual risks

- Existing local-file access is authorized by the trusted MCP caller; there is no multi-user isolation or new per-file consent UI.
- Initial private-network URL rejection is not a comprehensive network sandbox for yt-dlp redirects and site extractors. This is an existing limitation documented in the README; no broader SSRF protection is claimed.
- No dependency/advisory scanner was run. The upgrade introduced no package version changes; local dependency compatibility checks pass.
- No exhaustive concurrency stress test, malicious-codec corpus or all-provider image compatibility test was performed.
- The frame-difference selector and VLM can miss events or misestimate times. That is a quality limit, not proof that returned evidence is complete.
- Hash checks protect against accidental alteration within the tool's workflow; a local actor with permission to rewrite both code and task manifests is outside this trusted-local threat model.

## MCP package 0.3.0 review

Baseline: `e83a371ff05ee8c2d2f491ab33df870987ae6ca2`. Reviewed the server/installer relocation, compatibility launchers, package metadata, client examples and worker launch path. History/blame confirms per-job automatic llama startup, loopback-only binding, a random API key and GPU serialization already existed; they remain in place. New metadata pins direct dependencies to the already tested lockfile versions. No additional runtime dependency was introduced. Build tooling uses setuptools in an isolated build environment; no advisory scan was run.

Direct production callers: `configure_home` 1 (`main`), `worker_command` 1 (`submit`), `start_llama` 1 (`worker`), `main` 3 launch surfaces (console entry, module, compatibility script). The worker now executes the installed implementation using the current interpreter and passes the runtime directory explicitly, rather than assuming a virtualenv and source file in the data directory. Its argv still uses `subprocess.list2cmdline` with no shell. User-selected runtime directories are trusted configuration, not remotely supplied tool parameters. Existing input checks, image integrity checks and download checks are retained.

Reviewed failure modes include a data path containing spaces, worker survival after disconnect, backend unavailability, startup health delay and cleanup. Tests cover worker argv and backend startup failure/readiness; real installed-wheel MCP execution covers discovery, detached worker, GPU loading, evidence delivery and automatic shutdown. No new confirmed security finding. Existing SSRF, local filesystem trust and codec/dependency coverage limitations above still apply. Hard process kills/OS crashes are outside normal completion cleanup guarantees.
