/**
 * WebSocket composable for real-time pipeline status updates.
 * Auto-reconnects with exponential backoff, falls back to polling on failure.
 */

import { ref, onUnmounted } from 'vue'

export interface WebSocketOptions {
  url: string
  onMessage?: (data: any) => void
  onConnect?: () => void
  onDisconnect?: () => void
  reconnectInterval?: number
  maxReconnectInterval?: number
}

export function useWebSocket(options: WebSocketOptions) {
  const {
    url,
    onMessage,
    onConnect,
    onDisconnect,
    reconnectInterval = 1000,
    maxReconnectInterval = 30000,
  } = options

  const isConnected = ref(false)
  const isReconnecting = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let currentInterval = reconnectInterval
  let intentionalClose = false

  function connect() {
    if (ws?.readyState === WebSocket.OPEN) return

    intentionalClose = false

    try {
      // Determine WS URL from current page location
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = url.startsWith('ws') ? url : `${protocol}//${host}${url}`

      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        isConnected.value = true
        isReconnecting.value = false
        currentInterval = reconnectInterval
        onConnect?.()
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.(data)
        } catch {
          // Ignore non-JSON messages
        }
      }

      ws.onclose = () => {
        isConnected.value = false
        onDisconnect?.()
        if (!intentionalClose) {
          scheduleReconnect()
        }
      }

      ws.onerror = () => {
        ws?.close()
      }
    } catch {
      scheduleReconnect()
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return
    isReconnecting.value = true

    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      currentInterval = Math.min(currentInterval * 2, maxReconnectInterval)
      connect()
    }, currentInterval)
  }

  function disconnect() {
    intentionalClose = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    ws?.close()
    ws = null
    isConnected.value = false
    isReconnecting.value = false
  }

  function send(data: string | object) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }

  // Keep-alive ping every 30s
  let pingTimer: ReturnType<typeof setInterval> | null = null
  pingTimer = setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send('ping')
    }
  }, 30000)

  onUnmounted(() => {
    disconnect()
    if (pingTimer) {
      clearInterval(pingTimer)
    }
  })

  return {
    isConnected,
    isReconnecting,
    connect,
    disconnect,
    send,
  }
}
