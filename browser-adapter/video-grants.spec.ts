// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { grantVideoRead, hasVideoGrant, releaseVideoGrant } from '../src/background/video-grants.ts'

describe('watch consent scope', () => {
  it('never reuses approval across owners, tabs, documents or watch IDs', () => {
    const call = { id: 'x', name: 'browser_video_info', sessionId: 'owner', args: { companionId: '12345678-1234-4234-8234-123456789abc' } }
    const frames = [{ frameId: 0, parentFrameId: -1, documentId: 'doc-one', url: 'https://fixture.test' }]
    grantVideoRead(call, 10, frames)
    expect(hasVideoGrant(call, 10, frames)).toBe(true)
    expect(hasVideoGrant({ ...call, sessionId: 'other' }, 10, frames)).toBe(false)
    expect(hasVideoGrant(call, 11, frames)).toBe(false)
    expect(hasVideoGrant(call, 10, [{ ...frames[0]!, documentId: 'doc-two' }])).toBe(false)
    releaseVideoGrant(call); expect(hasVideoGrant(call, 10, frames)).toBe(false)
  })
})
