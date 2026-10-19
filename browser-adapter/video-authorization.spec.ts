// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { approvalPromptForCall } from '../src/background/authorization.ts'
import { dispatchToolCall } from '../src/background/tools.ts'

describe('video sharing boundary', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('blocks both video reads before touching a page when sharing is off', async () => {
    for (const name of ['browser_video_info', 'browser_capture_video']) {
      const result = await dispatchToolCall({ id: 'video-test', name, args: {} }, 'off')
      expect(result.ok).toBe(false); expect(result.error?.message).toContain('sharing is disabled')
    }
  })
  it('requests read permission for the selected video/audio frame', () => {
    const prompt = approvalPromptForCall({ id: 'video-test', name: 'browser_capture_video', args: {} }, 'ask',
      [{ frameId: 0, parentFrameId: -1, url: 'https://fixture.test/watch', documentId: 'fixture-document' }], 'en')
    expect(prompt?.kind).toBe('read'); expect(prompt?.origins).toEqual(['https://fixture.test'])
    expect(prompt?.summary).toContain('audio')
  })
  it('approves one watch once, then refuses a new document without another prompt', async () => {
    let documentId = 'document-one'
    const tab = { id: 10, url: 'https://fixture.test/watch' }
    const authorize = vi.fn(async () => 'approved' as const)
    vi.stubGlobal('chrome', { tabs: { sendMessage: vi.fn(async () => ({ ok: true, result: { text: 'video', videoState: {} } })) },
      webNavigation: { getAllFrames: vi.fn(async () => [{ frameId: 0, parentFrameId: -1, documentId, url: tab.url }]) } })
    const base = { id: 'watch-1', sessionId: 'owner', args: { companionId: '12345678-1234-4234-8234-123456789abc' } }
    expect((await dispatchToolCall({ ...base, name: 'browser_video_info', args: { ...base.args, watchConsent: true } }, 'ask', undefined, authorize, undefined, tab)).ok).toBe(true)
    expect((await dispatchToolCall({ ...base, name: 'browser_capture_video' }, 'ask', undefined, authorize, undefined, tab)).ok).toBe(true)
    expect(authorize).toHaveBeenCalledTimes(1)
    documentId = 'document-two'
    expect((await dispatchToolCall({ ...base, name: 'browser_video_info' }, 'ask', undefined, authorize, undefined, tab)).ok).toBe(false)
    expect(authorize).toHaveBeenCalledTimes(1)
    await dispatchToolCall({ ...base, name: 'browser_video_release' }, 'off')
  })
})
