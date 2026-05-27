import { defineStore } from 'pinia'
import { ref } from 'vue'

// API base URL - use relative path in development (Vite proxy), configurable in production
const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export const useDashboardStore = defineStore('dashboard', () => {
  const agents = ref<Record<string, any>>({})
  const approvalQueue = ref<any[]>([])
  const topics = ref<any[]>([])
  const config = ref<Record<string, any>>({})
  const budget = ref<Record<string, any> | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchPipeline() {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/pipeline/status`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      agents.value = data.agents || {}
      budget.value = data.budget || null
      error.value = null
    } catch (e: any) {
      console.error('fetchPipeline:', e)
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchApprovalQueue() {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/approval/queue`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      approvalQueue.value = data.articles || []
      error.value = null
    } catch (e: any) {
      console.error('fetchApprovalQueue:', e)
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchTopics() {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/topics`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      topics.value = data.topics || []
      error.value = null
    } catch (e: any) {
      console.error('fetchTopics:', e)
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchConfig() {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/config`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      config.value = data
      error.value = null
    } catch (e: any) {
      console.error('fetchConfig:', e)
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function approve(id: string, platforms: string[] = ['wechat']) {
    try {
      const res = await fetch(`${API_BASE}/api/approval/act`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'approve', target_id: id, platform_versions: platforms }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await fetchApprovalQueue()
      return res.json()
    } catch (e: any) {
      console.error('approve:', e)
      error.value = e.message
      throw e
    }
  }

  async function reject(id: string, reason: string) {
    try {
      const res = await fetch(`${API_BASE}/api/approval/act`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'reject', target_id: id, reason }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await fetchApprovalQueue()
      return res.json()
    } catch (e: any) {
      console.error('reject:', e)
      error.value = e.message
      throw e
    }
  }

  async function confirmTopic(id: string) {
    try {
      const res = await fetch(`${API_BASE}/api/topics/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'confirm', target_id: id }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await fetchTopics()
      return res.json()
    } catch (e: any) {
      console.error('confirmTopic:', e)
      error.value = e.message
      throw e
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    agents, 
    approvalQueue, 
    topics, 
    config, 
    budget,
    loading, 
    error,
    fetchPipeline, 
    fetchApprovalQueue, 
    fetchTopics, 
    fetchConfig,
    approve, 
    reject, 
    confirmTopic,
    clearError,
  }
})
