/**
 * Refresh and polling logic for the app shell.
 * Manages WebSocket connection, polling intervals, and bulk data refresh.
 * Extracted from App.vue to keep the root component slim.
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { useWebSocket } from './useWebSocket'

export function useAppRefresh() {
  const store = useDashboardStore()
  const isRefreshing = ref(false)
  let refreshInterval: ReturnType<typeof setInterval> | null = null

  const { isConnected, isReconnecting } = useWebSocket({
    url: '/ws/pipeline',
    apiKey: import.meta.env.VITE_API_KEY || '',
    onMessage: (data) => {
      store.handleWsMessage(data)
    },
    onConnect: () => {
      // When WS connects, reduce polling — WS handles pipeline live updates
      if (refreshInterval) {
        clearInterval(refreshInterval)
        refreshInterval = null
      }
      refreshInterval = setInterval(() => {
        if (document.visibilityState === 'visible') {
          store.fetchApprovalQueue()
          store.fetchTopics()
        }
      }, 30000)
    },
    onDisconnect: () => {
      // When WS disconnects, restore fast polling
      if (refreshInterval) {
        clearInterval(refreshInterval)
      }
      refreshInterval = setInterval(() => {
        if (document.visibilityState === 'visible') {
          store.fetchPipeline()
          store.fetchApprovalQueue()
        }
      }, 10000)
    },
  })

  /** Refresh all data sources simultaneously */
  async function refreshAll() {
    isRefreshing.value = true
    await Promise.all([
      store.fetchPipeline(),
      store.fetchApprovalQueue(),
      store.fetchTopics(),
      store.fetchConfig(),
    ])
    setTimeout(() => { isRefreshing.value = false }, 300)
  }

  onMounted(() => {
    store.fetchApprovalQueue()
    store.fetchTopics()
    store.fetchConfig()

    // Fallback polling for non-WS data
    refreshInterval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        store.fetchApprovalQueue()
        store.fetchTopics()
      }
    }, 30000)
  })

  onUnmounted(() => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  })

  return {
    isRefreshing,
    isConnected,
    isReconnecting,
    refreshAll,
  }
}
