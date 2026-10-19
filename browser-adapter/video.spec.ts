// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { videoAction } from '../src/content/video.ts'

describe('bounded media capture', () => {
  let v: HTMLVideoElement; let paused: boolean; let clock: number
  const stop = vi.fn()
  beforeEach(() => {
    vi.useFakeTimers(); document.body.innerHTML = '<video></video>'; v = document.querySelector('video')!; paused = false; clock = 0
    Object.defineProperties(v, { paused: { get: () => paused }, currentTime: { get: () => clock }, currentSrc: { value: 'blob:https://fixture.test/video' } })
    Object.assign(v, { captureStream: () => ({ getVideoTracks: () => [{}], getAudioTracks: () => [{}], getTracks: () => [{ stop }] }) })
    class Recorder {
      static isTypeSupported() { return true }
      state = 'inactive'; ondataavailable?: (e: { data: Blob }) => void; onstop?: () => void
      start() { this.state = 'recording'; clock = 2; this.ondataavailable?.({ data: new Blob([new Uint8Array(100)], { type: 'video/webm;codecs=vp8,opus' }) }) }
      stop() { this.state = 'inactive'; this.onstop?.() }
    }
    class Reader {
      result = ''; onload?: () => void
      readAsDataURL() { this.result = 'data:video/webm;codecs=vp8,opus;base64,' + 'AQID'.repeat(30); queueMicrotask(() => this.onload?.()) }
    }
    vi.stubGlobal('MediaRecorder', Recorder); vi.stubGlobal('FileReader', Reader); stop.mockClear()
  })
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })
  it('preserves all base64 after a MIME codec comma and stops owned tracks', async () => {
    const pending = videoAction('browser_capture_video', { seconds: 2 })
    await vi.advanceTimersByTimeAsync(2000)
    const result = await pending
    expect(result.videoClip?.data).toBe('AQID'.repeat(30)); expect(result.videoClip?.audio).toBe(true)
    expect(stop).toHaveBeenCalledOnce()
  })
  it('refuses paused playback without starting it', async () => {
    paused = true
    await expect(videoAction('browser_capture_video', {})).rejects.toThrow('paused')
  })
  it('selects the visible main player instead of an invisible first video', async () => {
    const other = document.createElement('video'); document.body.append(other)
    other.getBoundingClientRect = () => ({ left: 0, top: 0, right: 400, bottom: 300 }) as DOMRect
    expect((await videoAction('browser_video_info', {})).videoState?.index).toBe(1)
    expect((await videoAction('browser_video_info', { videoIndex: 0 })).videoState?.index).toBe(0)
  })
  it('discards a window on seek and releases its tracks', async () => {
    const pending = videoAction('browser_capture_video', {})
    const assertion = expect(pending).rejects.toThrow('Playback position')
    v.dispatchEvent(new Event('seeking')); await assertion
    expect(stop).toHaveBeenCalledOnce()
  })
})
