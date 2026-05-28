import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useToast } from '../composables/useToast'

// ═══════════════════════════════════════════════════════════════════════
// Type Definitions
// ═══════════════════════════════════════════════════════════════════════

export interface AgentStatus {
  agent: string
  stage?: string | number
  stage_name?: string
  progress_pct: number
  detail?: string
  error?: string | null
  timeout?: boolean
  started_at?: string
  completed_at?: string
  updated_at?: string
  worker?: string
  router?: boolean
  workers?: Record<string, WorkerStatus>
}

export interface WorkerStatus {
  status: 'running' | 'completed' | 'failed' | 'timeout' | 'skipped'
  stage?: number
  progress_pct?: number
  detail?: string
}

export interface ApprovalArticle {
  id: string
  meta: {
    topic?: string
    platform?: string
    proofread_score?: number
    critique_scores?: number[]
    revised_rounds?: number
    word_count?: number
    title_score?: number
    score?: number
    [key: string]: any
  }
  content_preview: string
  source: 'filesystem' | 'database'
  db_version_id?: number
}

export interface Topic {
  id: string
  filename?: string
  title: string
  description?: string
  url?: string
  source: string
  direction?: string
  final_score?: number
  viral_score?: number
  novelty_score?: number
  feasibility_score?: number
  saturation_score?: number
  attention_score?: number
  increment_score?: number
  source_weight?: number
  hot_value?: number
  [key: string]: any
}

export interface BudgetStatus {
  current_cost: number
  budget: number
  percentage: number
  is_warning: boolean
  is_exceeded: boolean
  remaining: number
}

export interface PipelineStatus {
  agents: Record<string, AgentStatus>
  timestamp: string
  budget: BudgetStatus
}

export interface ApprovalQueueResponse {
  articles: ApprovalArticle[]
  count: number
}

export interface TopicsResponse {
  topics: Topic[]
  count: number
}

export interface ConfigData {
  schedule?: Record<string, any>
  writing_styles?: Record<string, string>
  quality_gates?: Record<string, any>
  sources?: Record<string, { enabled: boolean; weight: number }>
  budget?: Record<string, any>
  model?: Record<string, any>
}

export interface ApprovalActionResponse {
  status: 'ok' | 'partial'
  action: string
  target_id: string
  path?: string
  warning?: string
}

export interface PipelineTrace {
  id: number
  session_id: number | null
  agent: string
  stage: string
  stage_name: string | null
  input_summary: string | null
  output_summary: string | null
  status: 'running' | 'completed' | 'failed' | 'skipped'
  duration_ms: number | null
  tokens_used: number
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface TraceSummary {
  stages: PipelineTrace[]
  total_tokens: number
  total_duration_ms: number
  failed_stages: string[]
  stage_count: number
}

export interface TraceSession {
  id: number
  date: string
  period: string
  topic: string
  status: string
  started_at: string | null
  completed_at: string | null
  stage_count: number
  total_tokens: number
  total_duration_ms: number
  failed_stages: string[]
}

export interface FlywheelData {
  recommended_thresholds: {
    proofread_threshold: number
    critique_threshold: number
    title_threshold: number
  }
  message: string
  sample_size: number
}

interface WsPipelineStatus {
  type: 'pipeline_status'
  agents?: Record<string, AgentStatus>
  budget?: BudgetStatus
}

// ═══════════════════════════════════════════════════════════════════════
// Store
// ═══════════════════════════════════════════════════════════════════════

// API base URL - use relative path in development (Vite proxy), configurable in production
const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export const useDashboardStore = defineStore('dashboard', () => {
  const toast = useToast()

  // ── State ─────────────────────────────────────────────────────────
  const agents = ref<Record<string, AgentStatus>>({})
  const approvalQueue = ref<ApprovalArticle[]>([])
  const topics = ref<Topic[]>([])
  const config = ref<ConfigData>({})
  const budget = ref<BudgetStatus | null>(null)
  const traceSessions = ref<TraceSession[]>([])
  const activeTraceSummary = ref<TraceSummary | null>(null)
  const flywheelData = ref<FlywheelData | null>(null)
  const error = ref<string | null>(null)

  // Track individual loading states
  const loadingStates = ref<Record<string, boolean>>({})

  // ── Computed ──────────────────────────────────────────────────────
  const loading = computed(() => Object.values(loadingStates.value).some(Boolean))
  const pendingCount = computed(() => approvalQueue.value.length)
  
  const isAgentRunning = computed(() => {
    return Object.values(agents.value).some(a => 
      a.progress_pct !== undefined && a.progress_pct < 100 && !a.error
    )
  })

  // ── Helper ────────────────────────────────────────────────────────
  async function fetchJson<T>(url: string, options?: RequestInit, retries = 2): Promise<T> {
    let lastError: Error | null = null
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const res = await fetch(`${API_BASE}${url}`, options)
        if (!res.ok) {
          const text = await res.text().catch(() => '')
          throw new Error(`HTTP ${res.status}: ${text || res.statusText}`)
        }
        return res.json()
      } catch (e) {
        lastError = e instanceof Error ? e : new Error(String(e))
        if (attempt < retries) {
          // Exponential backoff: 500ms, 1000ms
          await new Promise(r => setTimeout(r, 500 * Math.pow(2, attempt)))
        }
      }
    }
    throw lastError
  }

  function setLoading(key: string, value: boolean) {
    loadingStates.value[key] = value
  }

  function handleError(e: unknown, context: string): string {
    const message = e instanceof Error ? e.message : String(e)
    console.error(`[${context}]`, e)
    error.value = message
    return message
  }

  // ── Connection Status ────────────────────────────────────────────
  const connectionStatus = ref<'connected' | 'reconnecting' | 'disconnected'>('connected')
  let consecutiveFailures = 0

  function updateConnectionStatus(success: boolean) {
    if (success) {
      consecutiveFailures = 0
      connectionStatus.value = 'connected'
    } else {
      consecutiveFailures++
      if (consecutiveFailures >= 3) {
        connectionStatus.value = 'disconnected'
      } else {
        connectionStatus.value = 'reconnecting'
      }
    }
  }

  // ── Actions ───────────────────────────────────────────────────────

  function handleWsMessage(data: WsPipelineStatus) {
    if (data.type === 'pipeline_status') {
      agents.value = data.agents || {}
      budget.value = data.budget || null
      error.value = null
      updateConnectionStatus(true)
    }
  }

  async function fetchPipeline() {
    setLoading('pipeline', true)
    try {
      const data = await fetchJson<PipelineStatus>('/api/pipeline/status')
      agents.value = data.agents || {}
      budget.value = data.budget || null
      error.value = null
      updateConnectionStatus(true)
    } catch (e) {
      handleError(e, 'fetchPipeline')
      updateConnectionStatus(false)
    } finally {
      setLoading('pipeline', false)
    }
  }

  async function fetchApprovalQueue() {
    setLoading('approval', true)
    try {
      const data = await fetchJson<ApprovalQueueResponse>('/api/approval/queue')
      approvalQueue.value = data.articles || []
      error.value = null
    } catch (e) {
      handleError(e, 'fetchApprovalQueue')
    } finally {
      setLoading('approval', false)
    }
  }

  async function fetchTopics() {
    setLoading('topics', true)
    try {
      const data = await fetchJson<TopicsResponse>('/api/topics')
      topics.value = data.topics || []
      error.value = null
    } catch (e) {
      handleError(e, 'fetchTopics')
    } finally {
      setLoading('topics', false)
    }
  }

  async function fetchConfig() {
    setLoading('config', true)
    try {
      const data = await fetchJson<ConfigData>('/api/config')
      config.value = data
      error.value = null
    } catch (e) {
      handleError(e, 'fetchConfig')
    } finally {
      setLoading('config', false)
    }
  }

  async function approve(id: string, platforms: string[] = ['wechat']): Promise<ApprovalActionResponse> {
    setLoading('approve', true)
    try {
      const data = await fetchJson<ApprovalActionResponse>('/api/approval/act', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'approve', target_id: id, platform_versions: platforms }),
      })
      await fetchApprovalQueue()
      error.value = null
      toast.success('文章已批准，已推送到草稿箱')
      return data
    } catch (e) {
      handleError(e, 'approve')
      throw e
    } finally {
      setLoading('approve', false)
    }
  }

  async function reject(id: string, reason: string): Promise<ApprovalActionResponse> {
    setLoading('reject', true)
    try {
      const data = await fetchJson<ApprovalActionResponse>('/api/approval/act', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'reject', target_id: id, reason }),
      })
      await fetchApprovalQueue()
      error.value = null
      toast.info('文章已驳回，将安排重写')
      return data
    } catch (e) {
      handleError(e, 'reject')
      throw e
    } finally {
      setLoading('reject', false)
    }
  }

  async function confirmTopic(id: string): Promise<ApprovalActionResponse> {
    setLoading('confirmTopic', true)
    try {
      const data = await fetchJson<ApprovalActionResponse>('/api/topics/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'confirm', target_id: id }),
      })
      await fetchTopics()
      error.value = null
      toast.success('选题已确认，即将开始写作')
      return data
    } catch (e) {
      handleError(e, 'confirmTopic')
      throw e
    } finally {
      setLoading('confirmTopic', false)
    }
  }

  function clearError() {
    error.value = null
  }

  async function fetchTraceSessions(limit = 20) {
    setLoading('traces', true)
    try {
      const data = await fetchJson<{ sessions: TraceSession[] }>(`/api/pipeline/traces/sessions?limit=${limit}`)
      traceSessions.value = data.sessions || []
      error.value = null
    } catch (e) {
      handleError(e, 'fetchTraceSessions')
    } finally {
      setLoading('traces', false)
    }
  }

  async function fetchTraceSummary(sessionId: number) {
    setLoading('traceSummary', true)
    try {
      const data = await fetchJson<TraceSummary>(`/api/pipeline/traces/summary/${sessionId}`)
      activeTraceSummary.value = data
      error.value = null
    } catch (e) {
      handleError(e, 'fetchTraceSummary')
    } finally {
      setLoading('traceSummary', false)
    }
  }

  async function rerunFromStage(stage: number): Promise<void> {
    setLoading('rerun', true)
    try {
      await fetchJson('/api/pipeline/rerun', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage }),
      })
      toast.success(`从阶段 ${stage} 重新执行`)
      await fetchPipeline()
    } catch (e) {
      handleError(e, 'rerunFromStage')
      throw e
    } finally {
      setLoading('rerun', false)
    }
  }

  async function fetchFlywheel() {
    setLoading('flywheel', true)
    try {
      const data = await fetchJson<FlywheelData>('/api/config/quality-flywheel')
      flywheelData.value = data
      error.value = null
    } catch (e) {
      handleError(e, 'fetchFlywheel')
    } finally {
      setLoading('flywheel', false)
    }
  }

  function clearActiveTraceSummary() {
    activeTraceSummary.value = null
  }

  function isLoading(key: string): boolean {
    return loadingStates.value[key] || false
  }

  // ── Return ────────────────────────────────────────────────────────
  return {
    // State
    agents,
    approvalQueue,
    topics,
    config,
    budget,
    traceSessions,
    activeTraceSummary,
    flywheelData,
    loading,
    error,
    loadingStates,
    connectionStatus,

    // Computed
    pendingCount,
    isAgentRunning,

    // Actions
    handleWsMessage,
    fetchPipeline,
    fetchApprovalQueue,
    fetchTopics,
    fetchConfig,
    approve,
    reject,
    confirmTopic,
    clearError,
    isLoading,
    fetchTraceSessions,
    fetchTraceSummary,
    rerunFromStage,
    fetchFlywheel,
    clearActiveTraceSummary,
  }
})
