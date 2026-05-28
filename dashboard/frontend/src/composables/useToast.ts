import { ref } from 'vue'

export type ToastType = 'success' | 'error' | 'info' | 'warning'

export interface Toast {
  id: number
  type: ToastType
  message: string
  duration: number
}

const toasts = ref<Toast[]>([])
let nextId = 0

export function useToast() {
  function addToast(type: ToastType, message: string, duration = 3000) {
    const id = nextId++
    const toast: Toast = { id, type, message, duration }
    toasts.value.push(toast)

    if (duration > 0) {
      setTimeout(() => removeToast(id), duration)
    }
    // Cap at 5 toasts max
    if (toasts.value.length > 5) {
      toasts.value.shift()
    }
  }

  function removeToast(id: number) {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  function success(message: string, duration?: number) {
    addToast('success', message, duration)
  }

  function error(message: string, duration?: number) {
    addToast('error', message, duration ?? 5000)
  }

  function info(message: string, duration?: number) {
    addToast('info', message, duration)
  }

  function warning(message: string, duration?: number) {
    addToast('warning', message, duration ?? 4000)
  }

  return {
    toasts,
    addToast,
    removeToast,
    success,
    error,
    info,
    warning,
  }
}
