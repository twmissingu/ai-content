<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useDashboardStore } from './stores/dashboard'

const router = useRouter()
const route = useRoute()
const store = useDashboardStore()

const tabs = [
  { name: 'Pipeline', label: '📊 管线', path: '/pipeline' },
  { name: 'Approval', label: '📋 审批', path: '/approval' },
  { name: 'Topics', label: '🔥 选题', path: '/topics' },
  { name: 'Data', label: '📈 数据', path: '/data' },
  { name: 'Kb', label: '🗄️ 知识库', path: '/kb' },
]

onMounted(() => {
  store.fetchPipeline()
  store.fetchApprovalQueue()
  store.fetchTopics()
  store.fetchConfig()
  // Auto-refresh every 10s
  setInterval(() => {
    store.fetchPipeline()
    store.fetchApprovalQueue()
  }, 10000)
})
</script>

<template>
  <div style="min-height: 100vh; background: #f5f6fa;">
    <!-- Header -->
    <header style="background: #1a1a2e; color: white; padding: 0 24px; display: flex; align-items: center; height: 56px;">
      <h1 style="font-size: 18px; margin: 0; font-weight: 600;">稿定</h1>
      <span style="font-size: 12px; color: #8899aa; margin-left: 8px;">AI 内容生产系统</span>
    </header>

    <!-- Tab bar -->
    <nav style="background: white; border-bottom: 1px solid #e0e0e0; display: flex; padding: 0 16px;">
      <button
        v-for="tab in tabs"
        :key="tab.name"
        @click="router.push(tab.path)"
        :style="{
          padding: '12px 20px',
          border: 'none',
          background: 'transparent',
          fontSize: '14px',
          cursor: 'pointer',
          fontWeight: route.path === tab.path ? 600 : 400,
          color: route.path === tab.path ? '#1a73e8' : '#555',
          borderBottom: route.path === tab.path ? '2px solid #1a73e8' : '2px solid transparent',
        }"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- Content -->
    <main style="padding: 20px; max-width: 1200px; margin: 0 auto;">
      <router-view />
    </main>
  </div>
</template>
