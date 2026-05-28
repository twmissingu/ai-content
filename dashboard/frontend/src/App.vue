<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useDashboardStore } from './stores/dashboard'
import { useToast } from './composables/useToast'
import ErrorBoundary from './components/ErrorBoundary.vue'

const route = useRoute()
const store = useDashboardStore()
const toast = useToast()

const tabs = [
  { name: 'Pipeline', label: '管线', icon: '📊', path: '/pipeline' },
  { name: 'Approval', label: '审批', icon: '📋', path: '/approval', badge: true },
  { name: 'Topics', label: '选题', icon: '🔥', path: '/topics' },
  { name: 'Data', label: '数据', icon: '📈', path: '/data' },
  { name: 'Kb', label: '知识库', icon: '🗄️', path: '/kb' },
]

const isRefreshing = ref(false)
const isDark = ref(false)
let refreshInterval: ReturnType<typeof setInterval> | null = null

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

function toggleDark() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

// Forward store errors to toast
watch(() => store.error, (newError) => {
  if (newError) {
    toast.error(newError)
    store.clearError()
  }
})

onMounted(() => {
  // Restore theme preference
  const savedTheme = localStorage.getItem('theme')
  if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    isDark.value = true
    document.documentElement.classList.add('dark')
  }

  refreshAll()

  // Auto-refresh every 10s, but only when page is visible
  refreshInterval = setInterval(() => {
    if (document.visibilityState === 'visible') {
      store.fetchPipeline()
      store.fetchApprovalQueue()
    }
  }, 10000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
    refreshInterval = null
  }
})
</script>

<template>
  <div class="app-layout">
    <!-- Toast Notifications -->
    <div class="toast-container">
      <transition-group name="toast">
        <div
          v-for="t in toast.toasts.value"
          :key="t.id"
          class="toast-item"
          :class="`toast-${t.type}`"
          @click="toast.removeToast(t.id)"
        >
          <span class="toast-icon">
            {{ t.type === 'success' ? '✅' : t.type === 'error' ? '❌' : t.type === 'warning' ? '⚠️' : 'ℹ️' }}
          </span>
          <span class="toast-message">{{ t.message }}</span>
          <button class="toast-close" @click.stop="toast.removeToast(t.id)">✕</button>
        </div>
      </transition-group>
    </div>

    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <h1 class="header-logo">稿定</h1>
        <span class="header-subtitle">AI 内容生产系统</span>
      </div>
      <div class="header-right">
        <button
          class="btn btn-ghost btn-sm header-btn"
          @click="toggleDark"
          :title="isDark ? '切换亮色' : '切换暗色'"
        >
          {{ isDark ? '☀️' : '🌙' }}
        </button>
        <button
          class="btn btn-ghost btn-sm header-btn"
          :class="{ 'is-spinning': isRefreshing }"
          @click="refreshAll"
          title="刷新数据"
        >
          <span class="refresh-icon">🔄</span>
        </button>
      </div>
    </header>

    <!-- Navigation -->
    <nav class="app-nav">
      <div class="nav-container">
        <router-link
          v-for="tab in tabs"
          :key="tab.name"
          :to="tab.path"
          class="nav-item"
          :class="{ active: route.path === tab.path }"
        >
          <span class="nav-icon">{{ tab.icon }}</span>
          <span class="nav-label">{{ tab.label }}</span>
          <span 
            v-if="tab.badge && store.approvalQueue.length > 0" 
            class="nav-badge"
          >
            {{ store.approvalQueue.length }}
          </span>
        </router-link>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="app-main">
      <div class="content-container">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <ErrorBoundary>
              <component :is="Component" />
            </ErrorBoundary>
          </transition>
        </router-view>
      </div>
    </main>

    <!-- Mobile Bottom Navigation -->
    <nav class="mobile-nav">
      <router-link
        v-for="tab in tabs"
        :key="tab.name"
        :to="tab.path"
        class="mobile-nav-item"
        :class="{ active: route.path === tab.path }"
      >
        <span class="mobile-nav-icon">{{ tab.icon }}</span>
        <span class="mobile-nav-label">{{ tab.label }}</span>
        <span
          v-if="tab.badge && store.approvalQueue.length > 0"
          class="mobile-nav-badge"
        >
          {{ store.approvalQueue.length }}
        </span>
      </router-link>
    </nav>
  </div>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Toast Notifications ──────────────────────────────────────── */
.toast-container {
  position: fixed;
  top: var(--space-lg);
  right: var(--space-lg);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  max-width: 400px;
  width: 90%;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  cursor: pointer;
  pointer-events: auto;
  backdrop-filter: blur(8px);
}

.toast-success {
  background: var(--success-light);
  border: 1px solid var(--success);
}

.toast-error {
  background: var(--danger-light);
  border: 1px solid var(--danger);
}

.toast-warning {
  background: var(--warning-light);
  border: 1px solid var(--warning);
}

.toast-info {
  background: var(--info-light);
  border: 1px solid var(--info);
}

.toast-icon {
  font-size: var(--text-lg);
  flex-shrink: 0;
}

.toast-message {
  flex: 1;
  font-size: var(--text-sm);
  word-break: break-word;
}

.toast-success .toast-message { color: var(--success); }
.toast-error .toast-message { color: var(--danger); }
.toast-warning .toast-message { color: var(--warning-dark); }
.toast-info .toast-message { color: var(--info); }

.toast-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: var(--text-lg);
  padding: var(--space-xs);
  flex-shrink: 0;
  opacity: 0.6;
}

.toast-close:hover {
  opacity: 1;
}

.toast-enter-active {
  transition: all 0.3s ease-out;
}

.toast-leave-active {
  transition: all 0.2s ease-in;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

/* ── Header ──────────────────────────────────────────────────── */
.app-header {
  height: var(--header-height);
  background: var(--text-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-2xl);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.header-logo {
  font-size: var(--text-2xl);
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.5px;
}

.header-subtitle {
  font-size: var(--text-sm);
  color: rgba(255, 255, 255, 0.6);
  padding-left: var(--space-md);
  border-left: 1px solid rgba(255, 255, 255, 0.2);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.header-btn {
  color: rgba(255, 255, 255, 0.7);
  border-color: rgba(255, 255, 255, 0.2);
}

.header-btn:hover {
  color: white;
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.3);
}

.refresh-icon {
  display: inline-block;
  transition: transform var(--transition-slow);
}

.is-spinning .refresh-icon {
  animation: spin 0.8s linear;
}

/* ── Navigation ──────────────────────────────────────────────── */
.app-nav {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: var(--header-height);
  z-index: 99;
}

.nav-container {
  display: flex;
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: 0 var(--space-xl);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md) var(--space-lg);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: var(--text-md);
  font-weight: 500;
  border-bottom: 2px solid transparent;
  transition: all var(--transition-fast);
  position: relative;
}

.nav-item:hover {
  color: var(--primary);
  background: var(--bg-hover);
  text-decoration: none;
}

.nav-item.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
}

.nav-icon {
  font-size: var(--text-lg);
}

.nav-label {
  white-space: nowrap;
}

.nav-badge {
  background: var(--danger);
  color: white;
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  min-width: 18px;
  text-align: center;
  line-height: 1.4;
}

/* ── Main Content ────────────────────────────────────────────── */
.app-main {
  flex: 1;
  padding: var(--space-xl) var(--space-lg);
  /* Space for mobile bottom nav */
  padding-bottom: calc(var(--space-xl) + 60px);
}

.content-container {
  max-width: var(--content-max-width);
  margin: 0 auto;
}

/* ── Mobile Bottom Navigation ────────────────────────────────── */
.mobile-nav {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  z-index: 100;
  padding: var(--space-xs) 0;
  padding-bottom: env(safe-area-inset-bottom, var(--space-xs));
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
}

.mobile-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--space-xs) var(--space-sm);
  color: var(--text-tertiary);
  text-decoration: none;
  font-size: 10px;
  position: relative;
  transition: color var(--transition-fast);
}

.mobile-nav-item.active {
  color: var(--primary);
}

.mobile-nav-icon {
  font-size: 20px;
  line-height: 1;
}

.mobile-nav-label {
  font-weight: 500;
  line-height: 1;
}

.mobile-nav-badge {
  position: absolute;
  top: 0;
  right: 50%;
  transform: translateX(calc(50% + 10px));
  background: var(--danger);
  color: white;
  font-size: 9px;
  font-weight: 600;
  padding: 1px 4px;
  border-radius: var(--radius-full);
  min-width: 14px;
  text-align: center;
  line-height: 1.2;
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .app-header {
    padding: 0 var(--space-lg);
  }

  .header-subtitle {
    display: none;
  }

  /* Hide desktop nav on mobile */
  .app-nav {
    display: none;
  }

  /* Show mobile bottom nav */
  .mobile-nav {
    display: flex;
    justify-content: space-around;
  }

  .app-main {
    padding: var(--space-lg) var(--space-md);
    padding-bottom: calc(var(--space-lg) + 70px);
  }
}
</style>
