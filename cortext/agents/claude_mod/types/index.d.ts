export type CortextHit = { id: string; tier: string; text: string }
export type CortextRecall = { query: string; hits: CortextHit[]; ms: number }
export type CortextLevels = {
  working: number
  episodic: number
  semantic: number
  fading: number
  archived: number
}
export type CortextOverview = {
  ns: string
  memories: number
  levels: CortextLevels
  recallP50: number
  rememberP50: number
  stored: number
  queuePending: number
  queueDone: number
  queueFailed: number
}

declare module 'claude-code' {
  interface PluginState {
    cortext: {
      online: boolean
      overview: CortextOverview | null
      lastRecall: CortextRecall | null
    }
  }
}
