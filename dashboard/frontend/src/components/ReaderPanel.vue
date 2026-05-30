<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  url: string | null
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
const content = ref('')
const loading = ref(false)
const error = ref<string | null>(null)

async function fetchContent(url: string) {
  loading.value = true
  error.value = null
  content.value = ''
  try {
    const res = await fetch(`${API_BASE}/api/reader/fetch?url=${encodeURIComponent(url)}`)
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || `HTTP ${res.status}`)
    }
    const data = await res.json()
    content.value = data.content || ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : '抓取失败'
  } finally {
    loading.value = false
  }
}

watch(() => props.url, (newUrl) => {
  if (newUrl && props.visible) {
    fetchContent(newUrl)
  }
}, { immediate: true })

watch(() => props.visible, (vis) => {
  if (vis && props.url) {
    fetchContent(props.url)
  }
})
</script>

<template>
  <Transition name="slide">
    <div v-if="visible" class="reader-panel">
      <div class="reader-header">
        <h3 class="reader-title">原文阅读</h3>
        <button class="btn btn-ghost btn-sm" @click="emit('close')">✕</button>
      </div>
      <div v-if="url" class="reader-url">
        <a :href="url" target="_blank" rel="noopener" class="url-link">{{ url }}</a>
      </div>
      <div class="reader-body">
        <div v-if="loading" class="reader-loading">
          <div class="spinner"></div>
          <span>正在抓取原文...</span>
        </div>
        <div v-else-if="error" class="reader-error">
          <span>⚠️ {{ error }}</span>
          <button v-if="url" class="btn btn-ghost btn-sm" @click="url && fetchContent(url)">重试</button>
        </div>
        <pre v-else-if="content" class="reader-content">{{ content }}</pre>
        <div v-else class="reader-empty">暂无内容</div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.reader-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 480px;
  max-width: 90vw;
  height: 100vh;
  background: var(--bg-card);
  border-left: 1px solid var(--border-color);
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  display: flex;
  flex-direction: column;
}

.reader-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md) var(--space-lg);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.reader-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.reader-url {
  padding: var(--space-sm) var(--space-lg);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-hover);
}

.url-link {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  color: var(--primary);
  text-decoration: none;
  word-break: break-all;
}

.url-link:hover {
  text-decoration: underline;
}

.reader-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md);
}

.reader-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  padding: var(--space-4xl);
  color: var(--text-tertiary);
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.reader-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  padding: var(--space-lg);
  background: var(--danger-light);
  color: var(--danger);
  border-radius: var(--radius-md);
}

.reader-content {
  margin: 0;
  font-family: var(--font-family);
  font-size: var(--text-sm);
  line-height: 1.8;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.reader-empty {
  padding: var(--space-4xl);
  text-align: center;
  color: var(--text-tertiary);
}

/* ── Transition ─────────────────────────────────────────────── */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}

/* ── Responsive ─────────────────────────────────────────────── */
@media (max-width: 768px) {
  .reader-panel {
    width: 100vw;
  }
}
</style>
