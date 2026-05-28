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
  async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${url}`, options)
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`HTTP ${res.status}: ${text || res.statusText}`)
    }
    return res.json()
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

  // ── Actions ───────────────────────────────────────────────────────

  async function fetchPipeline() {
    setLoading('pipeline', true)
    try {
      const data = await fetchJson<PipelineStatus>('/api/pipeline/status')
      agents.value = data.agents || {}
      budget.value = data.budget || null
      error.value = null
    } catch (e) {
      handleError(e, 'fetchPipeline')
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
    loading,
    error,
    loadingStates,

    // Computed
    pendingCount,
    isAgentRunning,

    // Actions
    fetchPipeline,
    fetchApprovalQueue,
    fetchTopics,
    fetchConfig,
    approve,
    reject,
    confirmTopic,
    clearError,
    isLoading,
  }
})
