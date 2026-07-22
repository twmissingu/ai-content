<script setup lang="ts">
/**
 * App.vue — slim layout shell assembling the header, nav, router-view, and toast layer.
 * Tab/nav config extracted → composables/useAppTabs.ts
 * Refresh/polling logic extracted → composables/useAppRefresh.ts
 */
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useDashboardStore } from './stores/dashboard'
import { useToast } from './composables/useToast'
import { useAppTabs } from './composables/useAppTabs'
import { useAppRefresh } from './composables/useAppRefresh'
import ErrorBoundary from './components/ErrorBoundary.vue'

const route = useRoute()
const store = useDashboardStore()
const toast = useToast()
const { tabs } = useAppTabs()
const { isRefreshing, isConnected, isReconnecting, refreshAll } = useAppRefresh()

const isDark = ref(false)
const isThreeColumn = ref(false)

const connectionStatusText = computed(() => {
  if (isConnected.value) return '在线'
  if (isReconnecting.value) return '重连中'
  switch (store.connectionStatus) {
    case 'connected': return '在线'
    case 'reconnecting': return '重连中'
    case 'disconnected': return '离线'
    default: return '离线'
  }
})

function toggleDark() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

// Restore theme preference on mount
const savedTheme = localStorage.getItem('theme')
if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
  isDark.value = true
  document.documentElement.classList.add('dark')
}

// Forward store errors to toast
watch(() => store.error, (newError) => {
  if (newError) {
    toast.error(newError)
    store.clearError()
  }
})
</script>

<template>
  <div class="app-layout">
    <!-- Skip to Content (accessibility) -->
    <a href="#main-content" class="skip-to-content">跳转到主要内容</a>

    <!-- Live region for dynamic updates (screen readers) -->
    <div class="sr-only" aria-live="polite" aria-atomic="true" id="live-announcer"></div>

    <!-- Toast Notifications -->
    <div class="toast-container" aria-live="polite" aria-atomic="false" role="status">
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
          <button class="toast-close" @click.stop="toast.removeToast(t.id)" aria-label="关闭通知">✕</button>
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
        <!-- Connection Status Indicator -->
        <div
          class="connection-status"
          :class="isConnected ? 'connected' : isReconnecting ? 'reconnecting' : store.connectionStatus"
          :title="connectionStatusText"
          role="status"
          aria-live="polite"
          :aria-label="`连接状态: ${connectionStatusText}`"
        >
          <span class="status-dot"></span>
          <span class="status-text">{{ connectionStatusText }}</span>
        </div>

        <!-- Notification Bell -->
        <router-link
          to="/approval"
          class="notification-bell"
          :class="{ 'has-items': store.pendingCount > 0 }"
          title="待审批"
          aria-label="审批队列"
        >
          <span class="bell-icon">🔔</span>
          <span v-if="store.pendingCount > 0" class="bell-badge">
            {{ store.pendingCount > 99 ? '99+' : store.pendingCount }}
          </span>
        </router-link>

        <button
          class="btn btn-ghost btn-sm header-btn"
          @click="toggleDark"
          :title="isDark ? '切换亮色' : '切换暗色'"
          :aria-label="isDark ? '切换亮色主题' : '切换暗色主题'"
        >
          {{ isDark ? '☀️' : '🌙' }}
        </button>
        <button
          class="btn btn-ghost btn-sm header-btn"
          :class="{ 'is-spinning': isRefreshing }"
          @click="refreshAll"
          title="刷新数据"
          aria-label="刷新所有数据"
        >
          <span class="refresh-icon">🔄</span>
        </button>
        <button
          class="btn btn-ghost btn-sm header-btn"
          :class="{ active: isThreeColumn }"
          @click="isThreeColumn = !isThreeColumn"
          :title="isThreeColumn ? '单栏布局' : '三栏布局'"
          :aria-label="isThreeColumn ? '切换到单栏布局' : '切换到三栏布局'"
          :aria-pressed="isThreeColumn"
        >
          {{ isThreeColumn ? '◫' : '☰' }}
        </button>
      </div>
    </header>

    <!-- Navigation -->
    <nav class="app-nav" role="navigation" aria-label="主导航">
      <div class="nav-container">
        <router-link
          v-for="tab in tabs"
          :key="tab.name"
          :to="tab.path"
          class="nav-item"
          :class="{ active: route.path === tab.path }"
          :aria-label="`${tab.label}${route.path === tab.path ? ' (当前)' : ''}`"
          :aria-current="route.path === tab.path ? 'page' : undefined"
        >
          <span class="nav-icon">{{ tab.icon }}</span>
          <span class="nav-label">{{ tab.label }}</span>
          <span 
            v-if="tab.badge && store.approvalQueue.length > 0" 
            class="nav-badge"
            aria-live="polite"
          >
            {{ store.approvalQueue.length }}
          </span>
        </router-link>
      </div>
    </nav>

    <!-- Main Content -->
    <main id="main-content" class="app-main" :class="{ 'three-column': isThreeColumn }" role="main">
      <!-- Left Panel: Quick Stats (three-column mode only) -->
      <aside v-if="isThreeColumn" class="side-panel side-panel-left">
        <div class="side-panel-header">
          <h3 class="side-panel-title">📊 概览</h3>
        </div>
        <div class="side-panel-body">
          <div class="quick-stat">
            <span class="quick-stat-label">待审批</span>
            <span class="quick-stat-value">{{ store.approvalQueue.length }}</span>
          </div>
          <div class="quick-stat">
            <span class="quick-stat-label">候选选题</span>
            <span class="quick-stat-value">{{ store.topics.length }}</span>
          </div>
          <div class="quick-stat">
            <span class="quick-stat-label">管线状态</span>
            <span class="quick-stat-value status-indicator" :class="store.pipelineStatus.status">
              {{ store.pipelineStatus.status === 'running' ? '运行中' : store.pipelineStatus.status === 'completed' ? '已完成' : '空闲' }}
            </span>
          </div>
        </div>
      </aside>

      <div class="content-container">
        <ErrorBoundary>
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </ErrorBoundary>
      </div>

      <!-- Right Panel: Quick Actions (three-column mode only) -->
      <aside v-if="isThreeColumn" class="side-panel side-panel-right">
        <div class="side-panel-header">
          <h3 class="side-panel-title">⚡ 快捷</h3>
        </div>
        <div class="side-panel-body">
          <router-link to="/approval" class="quick-action">
            <span class="quick-action-icon">📋</span>
            <span>审批队列</span>
          </router-link>
          <router-link to="/topics" class="quick-action">
            <span class="quick-action-icon">🔥</span>
            <span>选题管理</span>
          </router-link>
          <router-link to="/sources" class="quick-action">
            <span class="quick-action-icon">📡</span>
            <span>信源流</span>
          </router-link>
          <router-link to="/kb" class="quick-action">
            <span class="quick-action-icon">🗄️</span>
            <span>知识库</span>
          </router-link>
        </div>
      </aside>
    </main>

    <!-- Mobile Bottom Navigation -->
    <nav class="mobile-nav" role="navigation" aria-label="底部导航">
      <router-link
        v-for="tab in tabs"
        :key="tab.name"
        :to="tab.path"
        class="mobile-nav-item"
        :class="{ active: route.path === tab.path }"
        :aria-label="`${tab.label}${route.path === tab.path ? ' (当前)' : ''}`"
        :aria-current="route.path === tab.path ? 'page' : undefined"
      >
        <span class="mobile-nav-icon">{{ tab.icon }}</span>
        <span class="mobile-nav-label">{{ tab.label }}</span>
        <span
          v-if="tab.badge && store.approvalQueue.length > 0"
          class="mobile-nav-badge"
          aria-live="polite"
        >
          {{ store.approvalQueue.length }}
        </span>
      </router-link>
    </nav>
  </div>
</template>

<style scoped>
/* ── Accessibility: Skip to Content ──────────────────────────── */
.skip-to-content {
  position: absolute;
  top: -100px;
  left: var(--space-md);
  background: var(--primary);
  color: white;
  padding: var(--space-sm) var(--space-lg);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  font-size: var(--text-md);
  font-weight: 500;
  z-index: 9999;
  transition: top 0.2s ease;
  text-decoration: none;
}

.skip-to-content:focus {
  top: 0;
  outline: 2px solid white;
  outline-offset: 2px;
}

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
  background: rgba(255, 253, 248, 0.86);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-2xl);
  position: sticky;
  top: 0;
  z-index: 100;
  border-bottom: 1px solid var(--border-light);
  backdrop-filter: blur(18px) saturate(1.05);
}

.dark .app-header {
  background: rgba(33, 31, 26, 0.86);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.header-logo {
  font-size: var(--text-2xl);
  font-weight: 720;
  margin: 0;
  letter-spacing: 0.08em;
}

.header-logo::after {
  content: '';
  display: inline-block;
  width: 26px;
  height: 1px;
  margin-left: var(--space-md);
  vertical-align: middle;
  background: var(--accent-line);
}

.header-subtitle {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  letter-spacing: 0.04em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.header-btn {
  min-width: 34px;
  color: var(--text-secondary);
  background: rgba(255, 253, 248, 0.52);
  border-color: var(--border-light);
}

.header-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
  border-color: var(--accent-line);
}

.header-btn.active {
  color: var(--primary);
  background: var(--primary-light);
  border-color: var(--primary);
}

.refresh-icon {
  display: inline-block;
  transition: transform var(--transition-slow);
}

.is-spinning .refresh-icon {
  animation: spin 0.8s linear;
}

/* ── Connection Status ──────────────────────────────────────── */
.connection-status {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: 560;
  background: var(--success-light);
  border: 1px solid rgba(95, 127, 99, 0.24);
}

.connection-status .status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 0 4px rgba(95, 127, 99, 0.12);
}

.connection-status.reconnecting {
  background: var(--warning-light);
  border-color: rgba(184, 135, 70, 0.28);
}

.connection-status.reconnecting .status-dot {
  background: var(--warning);
  animation: pulse 1.8s infinite;
  box-shadow: 0 0 0 4px rgba(184, 135, 70, 0.14);
}

.connection-status.disconnected {
  background: var(--danger-light);
  border-color: rgba(169, 84, 72, 0.28);
}

.connection-status.disconnected .status-dot {
  background: var(--danger);
  box-shadow: 0 0 0 4px rgba(169, 84, 72, 0.13);
}

.connection-status .status-text {
  color: var(--text-secondary);
}

/* ── Notification Bell ──────────────────────────────────────── */
.notification-bell {
  display: flex;
  align-items: center;
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-full);
  text-decoration: none;
  transition: background var(--transition-fast), transform var(--transition-fast);
  position: relative;
  opacity: 0.78;
}

.notification-bell:hover {
  background: var(--bg-hover);
  transform: translateY(-1px);
  opacity: 1;
}

.bell-icon {
  font-size: var(--text-lg);
  transition: transform var(--transition-fast);
  filter: grayscale(0.18);
}

.notification-bell.has-items .bell-icon {
  animation: bell-shake 0.5s ease-in-out;
}

@keyframes bell-shake {
  0%, 100% { transform: rotate(0); }
  25% { transform: rotate(6deg); }
  75% { transform: rotate(-6deg); }
}

.bell-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  background: var(--danger);
  color: #fffdf8;
  font-size: 9px;
  font-weight: 720;
  padding: 1px 4px;
  border-radius: var(--radius-full);
  min-width: 16px;
  text-align: center;
  line-height: 1.2;
  box-shadow: 0 0 0 2px var(--bg-card);
}

/* ── Navigation ──────────────────────────────────────────────── */
.app-nav {
  background: rgba(247, 243, 236, 0.82);
  border-bottom: 1px solid var(--border-light);
  position: sticky;
  top: var(--header-height);
  z-index: 99;
  backdrop-filter: blur(16px);
}

.dark .app-nav {
  background: rgba(23, 22, 19, 0.82);
}

.nav-container {
  display: flex;
  gap: var(--space-xs);
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-sm) var(--space-xl);
  overflow-x: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  min-height: 36px;
  padding: var(--space-sm) var(--space-lg);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: var(--text-md);
  font-weight: 560;
  border: 1px solid transparent;
  border-radius: var(--radius-full);
  transition: color var(--transition-fast), background var(--transition-fast), border-color var(--transition-fast), transform var(--transition-fast);
  position: relative;
}

.nav-item:hover {
  color: var(--text-primary);
  background: rgba(255, 253, 248, 0.68);
  border-color: var(--border-light);
  text-decoration: none;
}

.nav-item.active {
  color: var(--primary-dark);
  background: var(--bg-card);
  border-color: var(--border-color);
  box-shadow: var(--shadow-sm);
}

.nav-icon {
  font-size: var(--text-md);
  opacity: 0.58;
  filter: grayscale(0.25);
}

.nav-item.active .nav-icon {
  opacity: 0.82;
}

.nav-label {
  white-space: nowrap;
}

.nav-badge {
  background: var(--danger-light);
  color: var(--danger);
  font-size: var(--text-xs);
  font-weight: 650;
  padding: 1px 6px;
  border: 1px solid rgba(169, 84, 72, 0.2);
  border-radius: var(--radius-full);
  min-width: 18px;
  text-align: center;
  line-height: 1.4;
}

/* ── Main Content ────────────────────────────────────────────── */
.app-main {
  flex: 1;
  padding: var(--space-2xl) var(--space-lg);
  padding-bottom: calc(var(--space-2xl) + 60px);
}

.content-container {
  max-width: var(--content-max-width);
  margin: 0 auto;
  flex: 1;
  min-width: 0;
}

/* ── Three-Column Layout ────────────────────────────────────── */
.app-main.three-column {
  display: flex;
  gap: var(--space-lg);
  align-items: flex-start;
  max-width: calc(var(--content-max-width) + 520px);
  margin: 0 auto;
}

.side-panel {
  width: var(--sidebar-width);
  flex-shrink: 0;
  background: rgba(255, 253, 248, 0.62);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  position: sticky;
  top: calc(var(--header-height) + var(--nav-height) + var(--space-lg));
  max-height: calc(100vh - 150px);
  overflow-y: auto;
  box-shadow: var(--shadow-sm);
}

.side-panel-header {
  padding: var(--space-lg) var(--space-lg) var(--space-md);
  border-bottom: 1px solid var(--divider);
  background: transparent;
}

.side-panel-title {
  font-size: var(--text-sm);
  font-weight: 650;
  color: var(--text-secondary);
  margin: 0;
  letter-spacing: 0.04em;
}

.side-panel-title:first-letter,
.quick-action-icon {
  opacity: 0.62;
  filter: grayscale(0.25);
}

.side-panel-body {
  padding: var(--space-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.quick-stat {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md);
  border-radius: var(--radius-lg);
  background: rgba(250, 247, 240, 0.72);
  border: 1px solid transparent;
}

.quick-stat-label {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

.quick-stat-value {
  font-size: var(--text-sm);
  font-weight: 650;
  color: var(--text-primary);
}

.status-indicator.running {
  color: var(--primary);
}

.status-indicator.completed {
  color: var(--success);
}

.quick-action {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md);
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: var(--text-sm);
  transition: color var(--transition-fast), background var(--transition-fast), transform var(--transition-fast);
}

.quick-action:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
  transform: translateX(2px);
}

.quick-action-icon {
  font-size: var(--text-md);
}

/* ── Mobile Bottom Navigation ────────────────────────────────── */
.mobile-nav {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(255, 253, 248, 0.9);
  border-top: 1px solid var(--border-light);
  z-index: 100;
  padding: var(--space-xs) 0;
  padding-bottom: env(safe-area-inset-bottom, var(--space-xs));
  box-shadow: 0 -8px 24px rgba(64, 52, 39, 0.07);
  backdrop-filter: blur(16px);
}

.dark .mobile-nav {
  background: rgba(33, 31, 26, 0.9);
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
  transition: color var(--transition-fast), transform var(--transition-fast);
}

.mobile-nav-item.active {
  color: var(--primary);
  transform: translateY(-1px);
}

.mobile-nav-icon {
  font-size: 18px;
  line-height: 1;
  opacity: 0.7;
  filter: grayscale(0.25);
}

.mobile-nav-label {
  font-weight: 560;
  line-height: 1;
}

.mobile-nav-badge {
  position: absolute;
  top: 0;
  right: 50%;
  transform: translateX(calc(50% + 10px));
  background: var(--danger);
  color: #fffdf8;
  font-size: 9px;
  font-weight: 650;
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

  .header-logo::after,
  .header-subtitle {
    display: none;
  }

  .connection-status .status-text {
    display: none;
  }

  .app-nav {
    display: none;
  }

  .mobile-nav {
    display: flex;
    justify-content: space-around;
  }

  .app-main {
    padding: var(--space-lg) var(--space-md);
    padding-bottom: calc(var(--space-lg) + 70px);
  }

  .app-main.three-column {
    flex-direction: column;
  }

  .side-panel {
    display: none;
  }
}
</style>
