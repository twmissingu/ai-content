<script setup lang="ts">
import { ref, onErrorCaptured, onUnmounted } from 'vue'

const error = ref<Error | null>(null)
const errorInfo = ref('')
const retryCount = ref(0)
const autoRetrySeconds = ref(0)
let autoRetryTimer: ReturnType<typeof setInterval> | null = null
let countdownTimer: ReturnType<typeof setInterval> | null = null

const MAX_AUTO_RETRIES = 3

onErrorCaptured((err: Error, _instance, info: string) => {
  error.value = err
  errorInfo.value = info
  // Prevent error from propagating further
  return false
})

function clearTimers() {
  if (autoRetryTimer) { clearInterval(autoRetryTimer); autoRetryTimer = null }
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
}

function retry() {
  clearTimers()
  retryCount.value++
  error.value = null
  errorInfo.value = ''
  autoRetrySeconds.value = 0
}

function autoRetry() {
  if (retryCount.value >= MAX_AUTO_RETRIES) return
  autoRetrySeconds.value = 5
  countdownTimer = setInterval(() => {
    autoRetrySeconds.value--
    if (autoRetrySeconds.value <= 0) {
      clearInterval(countdownTimer!)
      countdownTimer = null
      retry()
    }
  }, 1000)
}

function reload() {
  clearTimers()
  window.location.reload()
}

async function copyError() {
  const text = `Error: ${error.value?.message}\nStack: ${error.value?.stack}\nInfo: ${errorInfo.value}`
  try {
    await navigator.clipboard.writeText(text)
    alert('错误信息已复制到剪贴板')
  } catch {
    // Fallback
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    alert('错误信息已复制到剪贴板')
  }
}

// Start auto-retry countdown when error appears
import { watch } from 'vue'
watch(error, (newError) => {
  if (newError && retryCount.value < MAX_AUTO_RETRIES) {
    autoRetry()
  }
})

onUnmounted(clearTimers)
</script>

<template>
  <div v-if="error" class="error-boundary">
    <div class="error-card card">
      <div class="error-icon">⚠️</div>
      <h2 class="error-title">页面加载出错</h2>
      <p class="error-message">{{ error.message || '发生了未知错误' }}</p>

      <div v-if="autoRetrySeconds > 0" class="auto-retry-hint">
        {{ autoRetrySeconds }} 秒后自动重试...
      </div>

      <div class="error-actions">
        <button class="btn btn-primary" @click="retry">
          重试
        </button>
        <button class="btn btn-ghost" @click="reload">
          刷新页面
        </button>
        <button class="btn btn-ghost btn-sm" @click="copyError" title="复制错误信息">
          📋 复制
        </button>
      </div>

      <div v-if="retryCount >= MAX_AUTO_RETRIES" class="max-retries-hint">
        已重试 {{ retryCount }} 次，建议刷新页面或检查网络连接
      </div>

      <details class="error-details">
        <summary>技术详情</summary>
        <pre>{{ errorInfo }}</pre>
        <pre>{{ error.stack }}</pre>
      </details>
    </div>
  </div>
  <slot v-else />
</template>

<style scoped>
.error-boundary {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: var(--space-xl);
}

.error-card {
  text-align: center;
  max-width: 500px;
  padding: var(--space-3xl);
}

.error-icon {
  font-size: 48px;
  margin-bottom: var(--space-lg);
}

.error-title {
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-md);
}

.error-message {
  color: var(--text-secondary);
  font-size: var(--text-md);
  margin: 0 0 var(--space-lg);
  line-height: 1.5;
}

.auto-retry-hint {
  color: var(--text-tertiary);
  font-size: var(--text-sm);
  margin-bottom: var(--space-lg);
}

.error-actions {
  display: flex;
  gap: var(--space-md);
  justify-content: center;
  margin-bottom: var(--space-xl);
}

.max-retries-hint {
  color: var(--warning-dark);
  font-size: var(--text-sm);
  margin-bottom: var(--space-lg);
  padding: var(--space-sm) var(--space-md);
  background: var(--warning-light);
  border-radius: var(--radius-md);
}

.error-details {
  text-align: left;
  margin-top: var(--space-lg);
}

.error-details summary {
  cursor: pointer;
  color: var(--text-tertiary);
  font-size: var(--text-sm);
  margin-bottom: var(--space-sm);
}

.error-details pre {
  background: var(--bg-hover);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  font-size: var(--text-xs);
  overflow-x: auto;
  color: var(--text-secondary);
  margin-top: var(--space-sm);
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 768px) {
  .error-card {
    padding: var(--space-xl);
  }

  .error-actions {
    flex-direction: column;
  }
}
</style>
