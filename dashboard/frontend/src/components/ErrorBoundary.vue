<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'

const error = ref<Error | null>(null)
const errorInfo = ref('')

onErrorCaptured((err: Error, instance, info: string) => {
  error.value = err
  errorInfo.value = info
  // Prevent error from propagating further
  return false
})

function retry() {
  error.value = null
  errorInfo.value = ''
}

function reload() {
  window.location.reload()
}
</script>

<template>
  <div v-if="error" class="error-boundary">
    <div class="error-card card">
      <div class="error-icon">⚠️</div>
      <h2 class="error-title">页面加载出错</h2>
      <p class="error-message">{{ error.message || '发生了未知错误' }}</p>
      <div class="error-actions">
        <button class="btn btn-primary" @click="retry">
          重试
        </button>
        <button class="btn btn-ghost" @click="reload">
          刷新页面
        </button>
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
  margin: 0 0 var(--space-xl);
  line-height: 1.5;
}

.error-actions {
  display: flex;
  gap: var(--space-md);
  justify-content: center;
  margin-bottom: var(--space-xl);
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
}
</style>
