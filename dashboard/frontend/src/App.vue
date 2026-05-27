<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useDashboardStore } from './stores/dashboard'

const router = useRouter()
const route = useRoute()
const store = useDashboardStore()

const tabs = [
  { name: 'Pipeline', label: '管线', icon: '📊', path: '/pipeline' },
  { name: 'Approval', label: '审批', icon: '📋', path: '/approval', badge: true },
  { name: 'Topics', label: '选题', icon: '🔥', path: '/topics' },
  { name: 'Data', label: '数据', icon: '📈', path: '/data' },
  { name: 'Kb', label: '知识库', icon: '🗄️', path: '/kb' },
]

const isRefreshing = ref(false)

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
  refreshAll()
  // Auto-refresh every 10s
  setInterval(() => {
    store.fetchPipeline()
    store.fetchApprovalQueue()
  }, 10000)
})
</script>

<template>
  <div class="app-layout">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <h1 class="header-logo">稿定</h1>
        <span class="header-subtitle">AI 内容生产系统</span>
      </div>
      <div class="header-right">
        <button 
          class="btn btn-ghost btn-sm" 
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
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
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
  gap: var(--space-md);
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
}

.content-container {
  max-width: var(--content-max-width);
  margin: 0 auto;
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .app-header {
    padding: 0 var(--space-lg);
  }
  
  .header-subtitle {
    display: none;
  }
  
  .nav-container {
    padding: 0 var(--space-sm);
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  
  .nav-item {
    padding: var(--space-md) var(--space-md);
    font-size: var(--text-sm);
  }
  
  .nav-icon {
    font-size: var(--text-md);
  }
  
  .app-main {
    padding: var(--space-lg) var(--space-md);
  }
}
</style>
