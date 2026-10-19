/** Controlled-page media only; no playback mutation or desktop/tab capture. */
export interface VideoState {
  page: string; source: string; index: number; currentTime: number;
  paused: boolean; ended: boolean; rate: number; width: number; height: number;
}
export interface VideoClip {
  data: string; mime: string; start: number; end: number; audio: boolean;
  state: VideoState;
}
let active = false
function selected(args: Record<string, unknown>): HTMLVideoElement {
  const videos = [...document.querySelectorAll('video')]
  const visible = videos.map((video, index) => {
    const r = video.getBoundingClientRect()
    const area = Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0)) * Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0))
    return { index, score: area * (!video.paused && !video.ended ? 2 : 1) }
  }).sort((a, b) => b.score - a.score)
  const index = args.videoIndex ?? visible[0]?.index ?? 0
  if (!Number.isInteger(index) || Number(index) < 0 || Number(index) >= videos.length) {
    throw new Error('No selected HTML5 video. Inspect the page/frame and videoIndex first.')
  }
  return videos[Number(index)]!
}
function state(v: HTMLVideoElement): VideoState {
  return { page: location.href, source: v.currentSrc, index: [...document.querySelectorAll('video')].indexOf(v),
    currentTime: v.currentTime, paused: v.paused, ended: v.ended, rate: v.playbackRate,
    width: v.videoWidth, height: v.videoHeight }
}
export async function videoAction(action: string, args: Record<string, unknown>): Promise<{
  text: string; videoAdapter?: string; videoState?: VideoState; videoClip?: VideoClip;
}> {
  const v = selected(args)
  if (action === 'browser_video_info') {
    return { text: 'Selected video state (page/source are untrusted data).', videoAdapter: 'dsh-video-companion/1', videoState: state(v) }
  }
  const seconds = args.seconds ?? 2
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 1 || seconds > 4) throw new Error('Capture duration must be 1–4 seconds.')
  if (active) throw new Error('A video capture is already active in this document.')
  if (v.paused || v.ended) throw new Error('Video is paused or ended. Capture never starts playback automatically.')
  if (v.playbackRate !== 1) throw new Error('Companion capture currently requires 1x playback for timestamp alignment.')
  if (v.mediaKeys) throw new Error('Protected media is not captured.')
  const capture = (v as HTMLVideoElement & { captureStream?: () => MediaStream }).captureStream
  if (!capture || typeof MediaRecorder === 'undefined') throw new Error('This browser does not support media-element capture.')
  active = true
  let stream: MediaStream | undefined
  try {
    stream = capture.call(v)
    if (!stream.getVideoTracks().length) throw new Error('No capturable video track; cross-origin/protected media may be unavailable.')
    const audio = stream.getAudioTracks().length > 0
    const mime = ['video/webm;codecs=vp8,opus', 'video/webm;codecs=vp8', 'video/webm'].find(x => MediaRecorder.isTypeSupported(x))
    if (!mime) throw new Error('No supported WebM recorder.')
    const recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 1_800_000, audioBitsPerSecond: 64_000 })
    const before = state(v); const chunks: Blob[] = []; let size = 0
    const blob = await new Promise<Blob>((resolve, reject) => {
      let failure: Error | undefined
      const stop = () => { if (recorder.state !== 'inactive') recorder.stop() }
      const invalidate = () => { failure = new Error('Playback position, source or document changed during capture; discard this window.'); stop() }
      const timer = setTimeout(stop, seconds * 1000)
      const events = ['seeking', 'ratechange', 'emptied']
      for (const event of events) v.addEventListener(event, invalidate)
      v.addEventListener('pause', stop); v.addEventListener('ended', stop); window.addEventListener('pagehide', invalidate)
      const clean = () => {
        clearTimeout(timer)
        for (const event of events) v.removeEventListener(event, invalidate)
        v.removeEventListener('pause', stop); v.removeEventListener('ended', stop); window.removeEventListener('pagehide', invalidate)
      }
      recorder.ondataavailable = event => {
        size += event.data.size
        if (size > 4 * 1024 * 1024) { failure = new Error('Capture exceeded 4 MiB.'); stop() }
        else if (event.data.size) chunks.push(event.data)
      }
      recorder.onerror = () => { failure = new Error('Browser recorder failed.'); stop() }
      recorder.onstop = () => { clean(); failure ? reject(failure) : resolve(new Blob(chunks, { type: mime })) }
      try { recorder.start(250) } catch (error) { clean(); reject(error) }
    })
    const after = state(v)
    if (after.source !== before.source || after.currentTime <= before.currentTime || blob.size < 64) throw new Error('No valid advancing video was captured.')
    const data = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => { const value = String(reader.result); const marker = value.indexOf(';base64,'); marker < 0 ? reject(new Error('Invalid encoded capture')) : resolve(value.slice(marker + 8)) }
      reader.onerror = reject; reader.readAsDataURL(blob)
    })
    return { text: 'Captured a bounded playback window. Timestamps are approximate player seconds.',
      videoClip: { data, mime, start: before.currentTime, end: after.currentTime, audio, state: after } }
  } finally {
    stream?.getTracks().forEach(track => track.stop()); active = false
  }
}
