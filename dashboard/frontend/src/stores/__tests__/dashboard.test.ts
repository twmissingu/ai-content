import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDashboardStore } from '../dashboard'

describe('useDashboardStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('has initial state', () => {
    const store = useDashboardStore()
    expect(store.agents).toEqual({})
    expect(store.approvalQueue).toEqual([])
    expect(store.topics).toEqual([])
    expect(store.config).toEqual({})
    expect(store.budget).toBeNull()
    expect(store.error).toBeNull()
  })

  it('computes pendingCount', () => {
    const store = useDashboardStore()
    expect(store.pendingCount).toBe(0)
    store.approvalQueue = [
      { id: '1', meta: {}, content_preview: '', source: 'filesystem' },
      { id: '2', meta: {}, content_preview: '', source: 'filesystem' },
    ]
    expect(store.pendingCount).toBe(2)
  })

  it('computes isAgentRunning', () => {
    const store = useDashboardStore()
    expect(store.isAgentRunning).toBe(false)
    store.agents = {
      scout: { agent: 'scout', progress_pct: 50 },
    }
    expect(store.isAgentRunning).toBe(true)
  })

  it('isAgentRunning false when all complete', () => {
    const store = useDashboardStore()
    store.agents = {
      scout: { agent: 'scout', progress_pct: 100 },
      writer: { agent: 'writer', progress_pct: 100 },
    }
    expect(store.isAgentRunning).toBe(false)
  })

  it('isAgentRunning false when agent has error', () => {
    const store = useDashboardStore()
    store.agents = {
      scout: { agent: 'scout', progress_pct: 50, error: 'timeout' },
    }
    expect(store.isAgentRunning).toBe(false)
  })

  it('clearError resets error', () => {
    const store = useDashboardStore()
    store.error = 'some error'
    store.clearError()
    expect(store.error).toBeNull()
  })

  it('isLoading tracks loading states', () => {
    const store = useDashboardStore()
    expect(store.isLoading('pipeline')).toBe(false)
    store.loadingStates['pipeline'] = true
    expect(store.isLoading('pipeline')).toBe(true)
  })

  it('computes loading from loadingStates', () => {
    const store = useDashboardStore()
    expect(store.loading).toBe(false)
    store.loadingStates['pipeline'] = true
    expect(store.loading).toBe(true)
  })

  it('fetchPipeline updates agents and budget', async () => {
    const store = useDashboardStore()
    const mockData = {
      agents: { scout: { agent: 'scout', progress_pct: 100 } },
      budget: { current_cost: 5, budget: 15, percentage: 33, is_warning: false, is_exceeded: false, remaining: 10 },
      timestamp: '2026-05-28T12:00:00Z',
    }
    vi.spyOn(global, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify(mockData), { status: 200 }))

    await store.fetchPipeline()
    expect(store.agents.scout.progress_pct).toBe(100)
    expect(store.budget?.budget).toBe(15)
    expect(store.error).toBeNull()
  })

  it('fetchPipeline handles error', async () => {
    const store = useDashboardStore()
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('network error'))

    await store.fetchPipeline()
    expect(store.error).toBeTruthy()
    expect(store.connectionStatus).toBe('reconnecting')
  })

  it('fetchApprovalQueue updates queue', async () => {
    const store = useDashboardStore()
    const mockData = {
      articles: [{ id: '1', meta: { topic: 'AI' }, content_preview: 'test', source: 'filesystem' }],
      count: 1,
    }
    vi.spyOn(global, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify(mockData), { status: 200 }))

    await store.fetchApprovalQueue()
    expect(store.approvalQueue).toHaveLength(1)
  })

  it('fetchTopics updates topics', async () => {
    const store = useDashboardStore()
    const mockData = {
      topics: [{ id: 't1', title: 'Test Topic', source: 'weibo' }],
      count: 1,
    }
    vi.spyOn(global, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify(mockData), { status: 200 }))

    await store.fetchTopics()
    expect(store.topics).toHaveLength(1)
    expect(store.topics[0].title).toBe('Test Topic')
  })

  it('fetchConfig updates config', async () => {
    const store = useDashboardStore()
    const mockData = { schedule: { morning_scout: '09:00' } }
    vi.spyOn(global, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify(mockData), { status: 200 }))

    await store.fetchConfig()
    expect(store.config.schedule?.morning_scout).toBe('09:00')
  })

  it('approve calls API and refreshes queue', async () => {
    const store = useDashboardStore()
    const approveResp = { status: 'ok', action: 'approve', target_id: 'art-1' }
    const queueResp = { articles: [], count: 0 }

    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(approveResp), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(queueResp), { status: 200 }))

    const result = await store.approve('art-1')
    expect(result.status).toBe('ok')
  })

  it('reject calls API and refreshes queue', async () => {
    const store = useDashboardStore()
    const rejectResp = { status: 'ok', action: 'reject', target_id: 'art-1' }
    const queueResp = { articles: [], count: 0 }

    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(rejectResp), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(queueResp), { status: 200 }))

    const result = await store.reject('art-1', 'AI腔太重')
    expect(result.status).toBe('ok')
  })

  it('confirmTopic calls API and refreshes topics', async () => {
    const store = useDashboardStore()
    const confirmResp = { status: 'ok', action: 'confirm', target_id: 't1' }
    const topicsResp = { topics: [], count: 0 }

    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(confirmResp), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(topicsResp), { status: 200 }))

    const result = await store.confirmTopic('t1')
    expect(result.status).toBe('ok')
  })

  it('approve throws on API error', async () => {
    const store = useDashboardStore()
    vi.spyOn(global, 'fetch').mockResolvedValueOnce(
      new Response('Server error', { status: 500 })
    )

    await expect(store.approve('bad-id')).rejects.toThrow()
    expect(store.error).toBeTruthy()
  })

  it('connectionStatus tracks failures', async () => {
    const store = useDashboardStore()
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('fail'))

    await store.fetchPipeline()
    expect(store.connectionStatus).toBe('reconnecting')

    await store.fetchPipeline()
    expect(store.connectionStatus).toBe('reconnecting')

    await store.fetchPipeline()
    expect(store.connectionStatus).toBe('disconnected')
  })

  it('connectionStatus resets on success', async () => {
    const store = useDashboardStore()
    store.connectionStatus = 'disconnected'

    const mockData = { agents: {}, budget: null, timestamp: '' }
    vi.spyOn(global, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify(mockData), { status: 200 }))

    await store.fetchPipeline()
    expect(store.connectionStatus).toBe('connected')
  })
})
