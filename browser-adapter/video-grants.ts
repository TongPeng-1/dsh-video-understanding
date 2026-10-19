/** Ephemeral read consent for one watch, owner, tab and exact document. */
import type { ToolCall } from './tools.ts'
import type { TabFrame } from './frames.ts'
const grants = new Map<string, { document: string; expires: number }>()
export function isCompanionRead(call: ToolCall): boolean {
  return ['browser_video_info', 'browser_capture_video'].includes(call.name) && key(call) !== undefined
}
function key(call: ToolCall): string | undefined {
  const id = call.args.companionId
  return call.sessionId && typeof id === 'string' && /^[a-f0-9-]{36}$/i.test(id) ? JSON.stringify([call.sessionId, id]) : undefined
}
function documentKey(call: ToolCall, tabId: number, frames: TabFrame[]): string | undefined {
  const frame = frames.find(f => f.frameId === (call.args.frame ?? 0))
  return frame?.documentId ? JSON.stringify([tabId, frame.frameId, frame.documentId, frame.url]) : undefined
}
export function hasVideoGrant(call: ToolCall, tabId: number, frames: TabFrame[]): boolean {
  const id = key(call); if (!id) return false
  const grant = grants.get(id)
  if (!grant || grant.expires < Date.now()) { grants.delete(id); return false }
  return grant.document === documentKey(call, tabId, frames)
}
export function grantVideoRead(call: ToolCall, tabId: number, frames: TabFrame[]): void {
  const id = key(call); const document = documentKey(call, tabId, frames)
  if (!id || !document) throw new Error('Companion consent requires an owning session and stable document.')
  if (grants.size >= 64 && !grants.has(id)) grants.delete(grants.keys().next().value!)
  grants.set(id, { document, expires: Date.now() + 30 * 60_000 })
}
export function releaseVideoGrant(call: ToolCall): void { const id = key(call); if (id) grants.delete(id) }
