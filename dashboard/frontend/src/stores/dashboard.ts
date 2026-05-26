import { defineStore } from 'pinia'
import { ref } from 'vue'

const API_BASE = 'http://localhost:8710'

export const useDashboardStore = defineStore('dashboard', () => {
  const agents = ref<Record<string, any>>({})
  const approvalQueue = ref<any[]>([])
  const topics = ref<any[]>([])
  const config = ref<Record<string, any>>({})
  const loading = ref(false)

  async function fetchPipeline() {
    try {
      const res = await fetch(`${API_BASE}/api/pipeline/status`)
      const data = await res.json()
      agents.value = data.agents
    } catch (e) {
      console.error('fetchPipeline:', e)
    }
  }

  async function fetchApprovalQueue() {
    try {
      const res = await fetch(`${API_BASE}/api/approval/queue`)
      const data = await res.json()
      approvalQueue.value = data.articles
    } catch (e) {
      console.error('fetchApprovalQueue:', e)
    }
  }

  async function fetchTopics() {
    try {
      const res = await fetch(`${API_BASE}/api/topics`)
      const data = await res.json()
      topics.value = data.topics
    } catch (e) {
      console.error('fetchTopics:', e)
    }
  }

  async function fetchConfig() {
    try {
      const res = await fetch(`${API_BASE}/api/config`)
      const data = await res.json()
      config.value = data
    } catch (e) {
      console.error('fetchConfig:', e)
    }
  }

  async function approve(id: string, platforms: string[] = ['wechat']) {
    const res = await fetch(`${API_BASE}/api/approval/act`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'approve', target_id: id, platform_versions: platforms }),
    })
    await fetchApprovalQueue()
    return res.json()
  }

  async function reject(id: string, reason: string) {
    const res = await fetch(`${API_BASE}/api/approval/act`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'reject', target_id: id, reason }),
    })
    await fetchApprovalQueue()
    return res.json()
  }

  async function confirmTopic(id: string) {
    const res = await fetch(`${API_BASE}/api/topics/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'confirm', target_id: id }),
    })
    await fetchTopics()
    return res.json()
  }

  return {
    agents, approvalQueue, topics, config, loading,
    fetchPipeline, fetchApprovalQueue, fetchTopics, fetchConfig,
    approve, reject, confirmTopic,
  }
})
