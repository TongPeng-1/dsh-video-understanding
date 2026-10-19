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

## Streaming backend 0.4.0 review

Baseline: `ce488317fc477ae82198b8ff4ce0822349fb7c32`. Scope includes every new runtime/bridge/compatibility/installer module, package metadata, the isolated dependency lock, model manifest, tests and relevant server callers. Risk is high at the new native/Python model-loading boundary; final outstanding confirmed security findings: 0 critical, 0 high, 0 medium, 0 low. Recommendation is conditional on the same trusted, single-user local deployment and pinned artifacts. This is not a codec or system security certification.

### Boundaries and history

- `submit` and runtime status are the two production callers of `selected_backend`; selection is a local enum in runtime configuration. The model cannot supply an executable or arbitrary backend command through MCP arguments. `stream_mode` accepts only caption/proactive.
- The worker is the sole production caller of the streaming subprocess bridge. The bridge is the sole production caller of stream result conversion and process-tree cleanup. Arguments remain lists, with no shell; media/question/ASR contents cannot become command syntax. ASR text is deliberately absent from the JSON request sent to the visual runner, covered by a regression test.
- Upstream VideoChat3 uses custom Python code. The official repository revision and SHA-256 manifest are fixed; runtime verifies the imported code/config before enabling `trust_remote_code`, uses local-only loading and an offline child environment, and installer verifies all three weight hashes. A local actor able to rewrite installed code and manifests remains outside this threat model.
- The compatibility layer explicitly binds omitted output-head weights to the trained embeddings, rejects unexplained checkpoint mismatches, preserves images only on initial generation steps, adapts the pinned video normalization/patch layout for pre-sampled RGB tensors, and computes the same block-diagonal vision attention in separate partitions. CPU FP32 and GPU BF16 comparisons pass. No arbitrary model kernel repository is selected by media input.
- Backend stdout is bounded JSONL with a bounded queue, fixed event types, monotonically bounded original-video intervals, cancellation checks and a deadline. Partial observations preserve streaming cursors. Native silence/standby is not interpreted as proof of no event. Caption truncation is marked as uncertainty.

### Findings resolved and verification

A cancellation resource leak was found during testing: Windows virtualenv launchers can leave the actual Python grandchild alive if only the launcher is terminated. Cleanup now stops the owned process tree using the Popen PID and an absolute system taskkill executable. A real multi-generation fixture verifies that the launcher and descendants all exit. No global Python processes or unrelated applications are killed.

Windows performance settings apply only to the inference process: explicit HighQoS and a temporary timer-resolution request, paired with normal-exit cleanup. They do not modify the user's power plan, registry, application permissions or other processes. Failed optional performance requests are diagnostic data, not elevated-permission requests.

The initial dependency scan flagged old Transformers/setuptools versions. The isolated runtime was updated to Transformers 5.10.4 and setuptools 84.0.0; pip-audit then reported no known vulnerabilities across its 46 installed packages. Official CUDA wheels are direct URLs with SHA-256 in the lockfile. The main MCP dependency versions are retained; build tooling is pinned to setuptools 84.0.0. An advisory check cannot establish that all transitive native decoders are safe for every crafted input.

30 unit tests cover input/mode restrictions, model-code verification, generation/weight compatibility, caption stopping, image evidence, stream cursors and cancellation delegation. Actual GPU, installed MCP and process-tree tests supplement the mocked coverage. Residual limitations from earlier reviews (trusted local file access, incomplete URL/redirect sandboxing, model errors, no malicious-codec corpus or exhaustive concurrency test) continue to apply.

## Browser companion 0.5.0 review

Baseline: `c190e213e69fdaa9c7ee2dee5f9bc3515108dc20`. Reviewed new browser capture/consent modules, host controller/native response hook, private resident service, runner branch and backed-up source installer, including nearby existing dispatch/authorization and model/agent callers. No additional dependency or network listener is introduced. No outstanding confirmed security finding was identified within this trusted-local scope; actual live-site integration remains unverified as recorded in validation.md.

- The single native watch tool owns capture and model subprocess lifecycle. Its command uses a fixed trusted runtime Python path and argv, with no shell or model-supplied executable. The existing GPU lock includes owned backend cleanup before unlock. Stop/dispose awaits only its owned process tree; ordinary Python/DSH processes are not globally terminated.
- Extension captures only the existing session-controlled tab/frame and selected HTML5 video. Normal read sharing/approval still applies. Ephemeral approval binds owner session, random watch ID, tab, frame and exact document/URL, expires after 30 minutes and is released on stop. It cannot transfer consent to another document; subsequent reads fail closed rather than prompting repeatedly. The original unrestrictedAccess semantics remain unchanged. No manifest permission is added.
- Clips are size bounded, checked for WebM magic at the host, written under host-generated paths, and canonicalized inside the watch directory at the service. Sequence/epoch/time bounds prevent reusing an old playback result. Keyframe payloads and decision output are bounded. These checks do not certify native decoders against crafted media or establish multi-user filesystem isolation.
- The decision route must explicitly declare image support. Derived image/text content is untrusted user data, not executable tool instructions. Persona comes from the owning session. The native stream hook requires that session's exact agent, owned companion message, selected provider/model and current epoch. Ordinary user turns and auxiliary calls pass through. A guard fix preserves empty normal tool-continuation steps rather than accidentally rejecting them. Queued/active stale companion output is removed or cancelled without dropping user inbox messages.
- Processed clips/WAVs are removed during normal operation. Stops/errors may retain the last pending clip, request and diagnostic logs in private watch storage; no automatic whole-directory purge or public upload occurs. Text and JPEGs are sent to the user's configured decision provider, which can be remote.
- Installer matches known source anchors, preserves backups, adds a native tool name to the existing video visibility group, and replaces only existing extension bundles. It does not install dependencies or change extension permissions. It is not transactional; failed builds can require restoring the recorded backups. Copying deployed files is not evidence of live registration.

Verification: 31 Python, 15 bridge and 46 extension selected tests; actual browser recording/pause/seek checks, resident GPU/ASR cleanup, real DSH image decisions and native publication via simulated browser transport. No new advisory scan was run because no dependency changed; the earlier isolated-environment scan does not cover every native codec. Full Bilibili/side-panel testing was blocked by browser debugger attachment, so site-specific behavior, hostile media and exhaustive concurrency remain outside verified coverage.

### 0.5.1 diagnostic follow-up

Reviewed against published `74767c3b452f7c410fb3139847570c789facce33`: private video replies now carry a fixed protocol marker; the host rejects missing markers/state and malformed playback fields before launching a backend. This changes error attribution, not browser access. Actual page inspection requires no new permissions and showed a normal VIDEO element; no closed-shadow/protected-media bypass is implemented. Added dispatcher regression coverage preserves state/clip fields rather than downgrading them to text. Updated guidance discourages speculative causes and an unrequested download fallback. No dependency, executable selection, authorization grant or network boundary changed; no new confirmed security issue identified. Real extension reload and successful site capture remain pending.

### 0.5.2 bounded handoff and local diagnostics

Reviewed against `06efc35408a71cc3747327e8f6e19825ffbbccd6`. The native publication path may reuse its owning session's immediate preflight for at most 250 ms, conservatively advancing playback time. Older preflights reread the controlled player. The same source, epoch, route and eight-second age bound still apply, and ended/paused/non-1x states are rejected. Pause/seek can occur just after any snapshot; this bounded race is inherent to sampled playback observation and is not an instantaneous event guarantee. No read consent, tab boundary or browser permission is changed.

Only successful publication now consumes the cooldown and enters reaction history. Diagnostic state stores counters/timings/rejection reasons plus an existing bounded error field under the watch's private directory; the last-event ring is capped at 24. It excludes media, transcripts, persona and candidate comments, and is not published. Tests cover the cache bound, conservative clock, expiration, generation changes, pauses and route changes; real DSH integration exercises a near-eight-second publish and an over-eight-second discard. No dependency changes or new confirmed security finding. Real-page visible publication remains pending.
