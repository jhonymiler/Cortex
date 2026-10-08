import type { On } from 'claude-code'
import { expect, mock, test } from 'claude-code/testing'

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
function engineBeneath(on: On, withClock = true) {
  if (withClock) {
    mock.clock(on)
  }
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
      : path === '/api/session/end' ? { jobs: [7] }
      : path === '/api/queue' ? { pending: 1, leased: 0, done: 4, failed: 0 }
      : path === '/api/queue/lease' ? (log.filter(r => r.url.endsWith('/api/queue/lease')).length === 1
        ? { id: 7, kind: 'extract', prompt: 'Part of an agent session: ...', system: 'json only', model: 'haiku' }
        : {})
      : path === '/api/queue/complete' ? { ok: true, added: ['f1'] }
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
    session: expect.any(String),
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

test('background worker runs queued jobs with the user\'s Haiku and returns the text', async ($, on) => {
  const log: { url: string; body?: string }[] = []
  const clock = mock.clock(on)
  engineBeneath(on, false)
  on('http.fetch', fakeDaemon(log))
  const asked: { model: string; prompt: string }[] = []
  on('model.complete', ($, e) => {
    asked.push({ model: e.model, prompt: e.prompt })
    return { value: { isAnswered: true, text: '{"facts": []}', usage: { input_tokens: 10, output_tokens: 5,
      cache_creation_input_tokens: 0, cache_read_input_tokens: 0 } } }
  })
  await $.session.start({ cwd: '/work/demo', surface: 'terminal', isInteractive: true })
  await clock.advance(20_000)
  expect(asked).toEqual([{ model: 'haiku', prompt: 'Part of an agent session: ...' }])
  const done = log.find(r => r.url.endsWith('/api/queue/complete'))
  expect(JSON.parse(done?.body ?? '{}')).toEqual({ id: 7, text: '{"facts": []}' })
})

test('turns carry a session id, and session end asks the daemon to abstract it', async ($, on) => {
  const log: { url: string; body?: string }[] = []
  engineBeneath(on)
  on('session.end', ($, e) => ({ sessionId: e.sessionId }))
  on('http.fetch', fakeDaemon(log))
  await $.session.start({ cwd: '/work/demo', surface: 'terminal', isInteractive: true })
  await $.prompt.submit({ text: 'deploy é na quarta agora', wait: false, origin: { kind: 'composer' } })
  await $.turn.complete({ answer: 'Anotado.', durationMs: 5, isAborted: false, turnId: 't9', reason: 'answer' })
  const turn = JSON.parse(log.find(r => r.url.endsWith('/api/turn'))?.body ?? '{}')
  expect(typeof turn.session).toBe('string')
  await $.session.end({ reason: 'clear', sessionId: 's-1', resume: undefined as never })
  const end = JSON.parse(log.find(r => r.url.endsWith('/api/session/end'))?.body ?? '{}')
  expect(end).toEqual({ ns: 'project:demo', session: turn.session })
})
