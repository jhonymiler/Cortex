import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

const RECALL = {
  context: '<cortext-memory>\n- payments-api | uses idempotency keys\n</cortext-memory>',
  packed: 'payments-api | uses idempotency keys',
  ms: 0.4,
  memories: [{ id: 'aaaaaaaa-1111', tier: 'semantic', what: 'uses idempotency keys', who: ['payments-api'], how: '' }],
}
const STATS = {
  levels: { working: 1, episodic: 2, semantic: 3, fading: 0, archived: 0 },
  graph: { total_memories: 6 },
  writes: { writes_total: 6 },
  latency: { recall: { p50_ms: 0.4 }, remember: { p50_ms: 0.7 } },
}

// What the engine does beneath the plugin, reduced to what this mod touches.
function engineBeneath(on: On) {
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('prompt.submit', ($, e) => ({ text: e.text, context: e.context }))
  on('turn.complete', ($, e) => ({ text: e.answer }))
  on('command.register', ($, e) => ({ value: { command: e.name } }))
  on('tool.register', ($, e) => ({ value: { tool: `mcp__cortext__${e.name}` } }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
}

function fakeDaemon(log: { url: string; body?: string }[]) {
  return async (_$: unknown, e: { url: string; init?: { body?: string } }) => {
    log.push({ url: e.url, body: e.init?.body })
    const path = new URL(e.url).pathname
    const reply: unknown =
      path === '/api/health' ? { ok: true }
      : path === '/api/ns' ? { ns: 'project:demo' }
      : path === '/api/stats' ? STATS
      : path === '/api/recall' ? RECALL
      : path === '/api/turn' ? { stored: true }
      : path === '/api/remember' ? { stored: true, id: 'bbbbbbbb-2222', status: 'OK', reason: '' }
      : null
    return { value: { status: reply ? 200 : 404, ok: reply !== null, headers: {}, text: JSON.stringify(reply) } }
  }
}

test('recalled memory is attached to the prompt, and the turn is stored', async ($, on) => {
  const log: { url: string; body?: string }[] = []
  engineBeneath(on)
  on('http.fetch', fakeDaemon(log))

  await $.session.start({ cwd: '/work/demo', surface: 'terminal', isInteractive: true })
  const submitted = await $.prompt.submit({ text: 'how do we avoid double charges?', wait: false, origin: { kind: 'composer' } })
  expect(submitted.context ?? []).toContain(RECALL.context)
  expect(submitted.text).toBe('how do we avoid double charges?')

  await $.turn.complete({ answer: 'We use idempotency keys.', durationMs: 10, isAborted: false, turnId: 't1', reason: 'answer' })
  const turn = log.find(r => r.url.endsWith('/api/turn'))
  expect(turn).toBeDefined()
  expect(JSON.parse(turn?.body ?? '{}')).toEqual({
    ns: 'project:demo',
    user: 'how do we avoid double charges?',
    assistant: 'We use idempotency keys.',
    agent: 'claude-code',
  })
})

test('slash commands are not sent to recall', async ($, on) => {
  const log: { url: string; body?: string }[] = []
  engineBeneath(on)
  on('http.fetch', fakeDaemon(log))
  await $.session.start({ cwd: '/work/demo', surface: 'terminal', isInteractive: true })
  const submitted = await $.prompt.submit({ text: '/memory', wait: false, origin: { kind: 'composer' } })
  expect(submitted.context ?? []).toEqual([])
  expect(log.some(r => r.url.endsWith('/api/recall'))).toBe(false)
})

test('with the daemon down the prompt passes through untouched', async ($, on) => {
  engineBeneath(on)
  on('http.fetch', () => ({ deny: 'connection refused' }))
  on('process.run', () => ({ value: { exitCode: 1, stdout: '', stderr: 'not found', isStdoutTruncated: false, isStderrTruncated: false } }))
  await $.session.start({ cwd: '/work/demo', surface: 'terminal', isInteractive: true })
  const submitted = await $.prompt.submit({ text: 'anything at all', wait: false, origin: { kind: 'composer' } })
  expect(submitted.text).toBe('anything at all')
  expect(submitted.context ?? []).toEqual([])
})

test('memory_remember tool stores through the daemon', async ($, on) => {
  const log: { url: string; body?: string }[] = []
  engineBeneath(on)
  on('http.fetch', fakeDaemon(log))
  await $.session.start({ cwd: '/work/demo', surface: 'terminal', isInteractive: true })
  const r = await $.tool.call({ tool: 'mcp__cortext__memory_remember', what: 'deploys go through Helm', importance: 0.9 })
  expect(String(r.result)).toContain('Stored bbbbbbbb')
  const sent = JSON.parse(log.find(x => x.url.endsWith('/api/remember'))?.body ?? '{}')
  expect(sent.what).toBe('deploys go through Helm')
  expect(sent.ns).toBe('project:demo')
})
