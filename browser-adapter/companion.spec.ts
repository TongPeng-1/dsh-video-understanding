import { describe, expect, it } from 'vitest'
import type { Context } from '@deepseek-ai/cordis'
import { parseDecision, validEvidence, registerVideoCompanion } from '../src/companion.ts'
import type { BridgeServer } from '../src/server.ts'

describe('companion freshness and turn isolation', () => {
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
