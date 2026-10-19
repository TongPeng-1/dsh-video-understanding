import { describe, expect, it } from 'vitest'
import type { Context } from '@deepseek-ai/cordis'
import { checkedVideoState, parseDecision, publicationState, replyRejection, validEvidence, registerVideoCompanion } from '../src/companion.ts'
import type { BridgeServer } from '../src/server.ts'

describe('companion freshness and turn isolation', () => {
  it('reuses only the immediate handoff preflight and keeps the eight-second limit', () => {
    const state = { page: 'https://fixture.test', source: 'blob:media', index: 0, currentTime: 17, paused: false, ended: false, rate: 1 }
    const identity = JSON.stringify([state.page, state.source])
    expect(publicationState(state, 1000, 1200)?.currentTime).toBe(17.2)
    expect(publicationState(state, 1000, 1251)).toBeUndefined()
    expect(replyRejection(publicationState(state, 1000, 1200), identity, 1, 1, 10, false, true)).toBeUndefined()
    expect(replyRejection({ ...state, currentTime: 18.1 }, identity, 1, 1, 10, false, true)).toBe('evidence_expired')
    expect(replyRejection(state, identity, 1, 2, 10, false, true)).toBe('playback_generation_changed')
    expect(replyRejection({ ...state, paused: true }, identity, 1, 1, 10, false, true)).toBe('paused')
    expect(replyRejection(state, identity, 1, 1, 10, false, false)).toBe('model_route_changed')
  })
  it('distinguishes a stripped or stale adapter reply from an empty media source', () => {
    const state = { page: 'https://fixture.test', source: '', index: 0, currentTime: 0, paused: true, ended: false, rate: 1 }
    expect(() => checkedVideoState({ text: 'Selected video state.' })).toThrow('protocol mismatch')
    expect(() => checkedVideoState({ videoState: state })).toThrow('protocol mismatch')
    expect(checkedVideoState({ videoAdapter: 'dsh-video-companion/1', videoState: state })).toBe(state)
    expect(() => checkedVideoState({ videoAdapter: 'dsh-video-companion/1', videoState: { ...state, currentTime: NaN } })).toThrow('invalid playback state')
  })
  it('rejects evidence from a previous seek or more than eight seconds ago', () => {
    const e = { epoch: 3, end: 12 } as Parameters<typeof validEvidence>[0]
    expect(validEvidence(e, 3, 14)).toBe(true)
    expect(validEvidence(e, 4, 14)).toBe(false)
    expect(validEvidence(e, 3, 21)).toBe(false)
    expect(validEvidence(e, 3, 8)).toBe(false)
  })
  it('accepts quiet decisions and refuses arbitrary decision states', () => {
    expect(parseDecision('{"state":"observe","comment":""}')).toEqual({ state: 'observe', comment: '' })
    expect(() => parseDecision('{"state":"run-command","comment":"do something"}')).toThrow()
  })
  it('does not reject ordinary empty continuation steps or user messages', async () => {
    const listeners = new Map<string, Function>()
    const ctx = { tools: { register: () => () => {} }, on: (event: string, fn: Function) => { listeners.set(event, fn); return () => {} } } as unknown as Context
    const dispose = registerVideoCompanion(ctx, {} as BridgeServer, 'unused')
    const guard = listeners.get('agent/pre-step')!
    const empty = { kind: 'enter', messages: [] }
    expect(await guard({ agent: { id: 'user-chat' } }, async () => empty)).toBe(empty)
    const user = { kind: 'enter', messages: [{ source: { kind: 'user' } }] }
    expect(await guard({ agent: { id: 'user-chat' } }, async () => user)).toBe(user)
    const stale = { kind: 'enter', messages: [{ source: { kind: 'video-companion', watchId: 'old', epoch: 0 } }] }
    expect(await guard({ agent: { id: 'user-chat' } }, async () => stale)).toEqual({ kind: 'reject' })
    dispose()
  })
})
