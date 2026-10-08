import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { CortextHit, CortextLevels, CortextOverview, CortextRecall } from '../types'

// Cortext for Claude Code, as function hooks:
//   prompt.submit  -> recall from the local daemon, attach as context the model reads
//   turn.complete  -> store the finished exchange as a memory
//   session.start  -> start the daemon if needed, register memory tools and /memory
//   /memory        -> a pane with the memory levels, the last recall and latency
// Everything goes through the daemon (cortext-memory serve) over 127.0.0.1;
// when it can't be reached the hooks step aside and the session runs as usual.

const PANE = 'cortext'
const online = atom({ plugin: 'cortext', key: 'online' } as const, false)
const overview = atom({ plugin: 'cortext', key: 'overview' } as const, null)
const lastRecall = atom({ plugin: 'cortext', key: 'lastRecall' } as const, null)

const TIERS: (keyof CortextLevels)[] = ['working', 'episodic', 'semantic', 'fading', 'archived']
const TIER_LABEL: Record<keyof CortextLevels, string> = {
  working: 'trabalho',
  episodic: 'episódica',
  semantic: 'semântica',
  fading: 'esmaecendo',
  archived: 'arquivada',
}
const TIER_COLOR: Record<keyof CortextLevels, string> = {
  working: '#f5c542',
  episodic: '#4fb3ff',
  semantic: '#9b7bff',
  fading: '#8a8f98',
  archived: '#4a4f57',
}

type Options = { port?: number; command?: string; inject?: boolean }
type RecallReply = { context: string; ms: number; memories: { id: string; tier: string; what: string; who: string[]; how: string }[] }
type StatsReply = {
  levels: CortextLevels
  graph: { total_memories: number }
  writes: { writes_total: number }
  latency: { recall: { p50_ms: number }; remember: { p50_ms: number } }
}

// Set by register(); module state is rebuilt on every (re)load.
let base = 'http://127.0.0.1:7077'
let ns = 'default'
let lastPrompt = ''

async function api<T>($: EngineInterface, path: string, body?: unknown, method?: string): Promise<T | null> {
  try {
    const res = await $.http.fetch(
      base + path,
      body === undefined && method === undefined
        ? undefined
        : {
            method: method ?? 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body === undefined ? undefined : JSON.stringify(body),
          },
    )
    return res.ok ? (JSON.parse(res.text) as T) : null
  } catch {
    return null
  }
}

async function refresh($: EngineInterface): Promise<void> {
  const s = await api<StatsReply>($, `/api/stats?ns=${encodeURIComponent(ns)}`)
  await update($, online, () => s !== null)
  if (s === null) {
    $.ui.status(undefined)
    return
  }
  const view: CortextOverview = {
    ns,
    memories: s.graph.total_memories,
    levels: s.levels,
    recallP50: s.latency.recall.p50_ms,
    rememberP50: s.latency.remember.p50_ms,
    stored: s.writes.writes_total,
  }
  await update($, overview, () => view)
  $.ui.status(`◆ cortext ${view.memories} mem`)
}

export const register: Register = (on, options) => {
  const opts = (options ?? {}) as Options
  base = `http://127.0.0.1:${Number(opts.port) || 7077}`
  const inject = opts.inject !== false

  on('session.start', async ($, e, next) => {
    let health = await api<{ ok: boolean }>($, '/api/health')
    if (health === null) {
      try {
        await $.process.run([opts.command || 'cortext-memory', 'daemon', 'start'], { timeoutMs: 8000 })
      } catch {
        // not installed or not on PATH: the session runs without memory
      }
      health = await api<{ ok: boolean }>($, '/api/health')
    }
    if (health !== null) {
      const r = await api<{ ns: string }>($, `/api/ns?cwd=${encodeURIComponent(e.cwd)}`)
      ns = r?.ns ?? 'default'
      await $.tool.register({
        name: 'memory_recall',
        description:
          "Search this project's long-term memory (Cortext) for facts relevant to a query: past decisions, conventions, fixes, preferences. Relevant memories are already attached to each prompt; call this to dig deeper.",
        inputSchema: {
          type: 'object',
          properties: { query: { type: 'string' }, max_results: { type: 'number' } },
          required: ['query'],
        },
      })
      await $.tool.register({
        name: 'memory_remember',
        description:
          'Store one durable fact in long-term memory: a decision and its reason, a convention, the fix for a recurring problem, where something lives, a user preference. One concise sentence; never secrets.',
        inputSchema: {
          type: 'object',
          properties: {
            what: { type: 'string', description: 'The fact.' },
            why: { type: 'string' },
            how: { type: 'string' },
            who: { type: 'array', items: { type: 'string' } },
            importance: { type: 'number', minimum: 0, maximum: 1 },
          },
          required: ['what'],
        },
      })
      await $.tool.register({
        name: 'memory_forget',
        description: 'Delete a memory by its id when a recalled fact is wrong or obsolete.',
        inputSchema: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] },
      })
      await refresh($)
    }
    await $.command.register({ name: 'memory', description: 'Cortext: memory levels, last recall, latency' })
    return next(e)
  })

  on('prompt.submit', async ($, e, next) => {
    const text = e.text.trim()
    if (!inject || text.length < 3 || text.startsWith('/') || !(await read($, online))) {
      return next(e)
    }
    lastPrompt = text
    const r = await api<RecallReply>($, '/api/recall', { ns, query: text.slice(0, 2000), max_results: 6, max_tokens: 350 })
    if (r === null) {
      return next(e)
    }
    const hits: CortextHit[] = r.memories.map(m => ({
      id: m.id,
      tier: m.tier,
      text: (m.who.length ? m.who.join(', ') + ' | ' : '') + m.what,
    }))
    const recall: CortextRecall = { query: text.slice(0, 120), hits, ms: r.ms }
    await update($, lastRecall, () => recall)
    if (!r.context) {
      return next(e)
    }
    return next({ ...e, context: [...(e.context ?? []), r.context] })
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId === undefined && e.reason === 'answer' && lastPrompt && (await read($, online))) {
      await api($, '/api/turn', { ns, user: lastPrompt, assistant: e.answer, agent: 'claude-code' })
      lastPrompt = ''
      await refresh($)
    }
    return result
  })

  on('tool.call', { tool: 'mcp__cortext__memory_recall' }, async ($, e) => {
    const r = await api<RecallReply>($, '/api/recall', {
      ns,
      query: String(e.query ?? ''),
      max_results: Number(e.max_results ?? 8),
      max_tokens: 800,
    })
    if (r === null) {
      return { result: 'Cortext daemon unavailable.' }
    }
    const lines = r.memories.map(
      m => `[${m.id.slice(0, 8)}] (${m.tier}) ${m.who.length ? m.who.join(', ') + ' | ' : ''}${m.what}${m.how ? ' → ' + m.how.slice(0, 200) : ''}`,
    )
    return { result: lines.length ? lines.join('\n') : 'No relevant memories.' }
  })

  on('tool.call', { tool: 'mcp__cortext__memory_remember' }, async ($, e) => {
    const r = await api<{ stored: boolean; id: string | null; status: string; reason: string }>($, '/api/remember', {
      ns,
      what: String(e.what ?? ''),
      why: e.why ? String(e.why) : undefined,
      how: e.how ? String(e.how) : undefined,
      who: Array.isArray(e.who) ? e.who.map(String) : undefined,
      importance: typeof e.importance === 'number' ? e.importance : 0.7,
    })
    await refresh($)
    if (r === null) {
      return { result: 'Cortext daemon unavailable.' }
    }
    return { result: r.stored ? `Stored ${String(r.id).slice(0, 8)}${r.status === 'WARN' ? ` (warning: ${r.reason})` : ''}` : `Not stored: ${r.reason}` }
  })

  on('tool.call', { tool: 'mcp__cortext__memory_forget' }, async ($, e) => {
    const id = String(e.id ?? '')
    const r = await api<{ deleted: boolean }>($, `/api/memory/${encodeURIComponent(id)}?ns=${encodeURIComponent(ns)}`, undefined, 'DELETE')
    await refresh($)
    if (r === null) {
      return { result: 'Cortext daemon unavailable, or no such memory.' }
    }
    return { result: r.deleted ? 'Deleted.' : 'No such memory (use the full id).' }
  })

  on('command.run', { command: 'memory' }, async $ => {
    await refresh($)
    await $.ui.open({ id: PANE, title: 'Cortext memory' })
    const view = await read($, overview)
    return { text: view ? `Cortext: ${view.memories} memories in ${view.ns}.` : 'Cortext daemon is not running (cortext-memory daemon start).' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button, Link } = $.ui.resolve(e)
    const view = await read($, overview)
    const recall = await read($, lastRecall)
    const width = Math.max(20, (e.props.bodyColumns ?? 60) - 22)

    if (!(await read($, online)) || view === null) {
      return (
        <Box flexDirection="column">
          <Text color="warning">Cortext daemon offline.</Text>
          <Text dimColor>Start it with: cortext-memory daemon start</Text>
          <Button key="retry" label="Retry" onPress={() => refresh($)} />
        </Box>
      )
    }

    const max = Math.max(1, ...TIERS.map(t => view.levels[t]))
    return (
      <Box flexDirection="column" gap={1}>
        <Box flexDirection="column">
          <Text bold>
            {view.ns} · {view.memories} memories
          </Text>
          <Text dimColor>
            recall p50 {view.recallP50} ms · write p50 {view.rememberP50} ms
          </Text>
        </Box>
        <Box flexDirection="column">
          {TIERS.map(t => {
            const n = view.levels[t]
            const bar = '█'.repeat(Math.round((n / max) * width)) || (n > 0 ? '▏' : '')
            return (
              <Box key={t}>
                <Box width={12}>
                  <Text>{TIER_LABEL[t]}</Text>
                </Box>
                <Text color={TIER_COLOR[t]}>{bar}</Text>
                <Text dimColor> {n}</Text>
              </Box>
            )
          })}
        </Box>
        {recall && (
          <Box flexDirection="column">
            <Text bold>
              Last recall · {recall.hits.length} hits · {recall.ms} ms
            </Text>
            <Text dimColor wrap="truncate">
              “{recall.query}”
            </Text>
            {recall.hits.map(h => (
              <Box key={h.id}>
                <Text color={TIER_COLOR[h.tier as keyof CortextLevels] ?? 'gray'}>● </Text>
                <Text wrap="truncate">{h.text}</Text>
              </Box>
            ))}
          </Box>
        )}
        <Box gap={2}>
          <Button key="refresh" label="Refresh" hotkey="r" onPress={() => refresh($)} />
          <Button
            key="dream"
            label="Consolidate"
            hotkey="c"
            onPress={async () => {
              await api($, '/api/dream', { ns })
              await refresh($)
              $.ui.toast('Cortext: consolidation cycle done')
            }}
          />
          <Link href={base} label="Open dashboard" />
        </Box>
      </Box>
    )
  })
}
