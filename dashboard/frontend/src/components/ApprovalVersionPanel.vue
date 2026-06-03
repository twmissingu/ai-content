<script setup lang="ts">
/**
 * ApprovalVersionPanel — platform version management for database-tracked articles.
 * Extracted from ApprovalView.vue to reduce its size.
 * Displays per-platform versions and allows approve/reject on each.
 */
import { ref, watch } from 'vue'
import { useToast } from '../composables/useToast'
import SkeletonLoader from './SkeletonLoader.vue'
import { API_BASE } from '../utils/api'

interface PlatformVersion {
  id: number
  session_id: number
  platform: string
  status: string
  score: number | null
  content_path: string | null
}

const props = defineProps<{
  sessionId: number | null | undefined
}>()

const toast = useToast()

const versions = ref<PlatformVersion[]>([])
const loading = ref(false)
const processingIds = ref<Set<number>>(new Set())

async function fetchVersions() {
  const sid = props.sessionId
  if (!sid) return
  loading.value = true
  try {
    
    const res = await fetch(`${API_BASE}/api/approval/versions/${sid}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    versions.value = data.versions || []
  } catch (e) {
    toast.error(`获取版本列表失败: ${e instanceof Error ? e.message : '未知错误'}`)
    versions.value = []
  } finally {
    loading.value = false
  }
}

async function approveVersion(versionId: number) {
  processingIds.value.add(versionId)
  try {
    
    const res = await fetch(`${API_BASE}/api/approval/version/${versionId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    toast.success('版本已批准')
    const v = versions.value.find(v => v.id === versionId)
    if (v) v.status = 'approved'
  } catch (e) {
    toast.error(`批准失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    processingIds.value.delete(versionId)
  }
}

async function rejectVersion(versionId: number) {
  processingIds.value.add(versionId)
  try {
    
    const res = await fetch(`${API_BASE}/api/approval/version/${versionId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    toast.success('版本已驳回')
    const v = versions.value.find(v => v.id === versionId)
    if (v) v.status = 'rejected'
  } catch (e) {
    toast.error(`驳回失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    processingIds.value.delete(versionId)
  }
}

watch(() => props.sessionId, (id) => {
  if (id) {
    versions.value = []
    fetchVersions()
  } else {
    versions.value = []
  }
}, { immediate: true })
</script>

<template>
  <div class="versions-section">
    <div class="versions-header">
      <span class="versions-title">平台版本管理</span>
      <button
        class="btn btn-ghost btn-sm"
        :disabled="loading"
        aria-label="刷新版本列表"
        @click="fetchVersions"
      >
        {{ loading ? '加载中...' : '刷新版本' }}
      </button>
    </div>

    <div v-if="loading" class="versions-loading">
      <SkeletonLoader type="text" :count="2" />
    </div>

    <div v-else-if="versions.length > 0" class="versions-list">
      <div
        v-for="version in versions"
        :key="version.id"
        class="version-item"
        :class="`version-${version.status}`"
      >
        <div class="version-info">
          <span class="version-platform">{{ version.platform }}</span>
          <span class="version-status">{{ version.status }}</span>
          <span v-if="version.score" class="version-score">评分: {{ version.score }}</span>
        </div>
        <div class="version-actions">
          <button
            v-if="version.status === 'pending'"
            class="btn btn-success btn-sm"
            :disabled="processingIds.has(version.id)"
            :aria-label="`批准 ${version.platform} 版本`"
            @click="approveVersion(version.id)"
          >
            {{ processingIds.has(version.id) ? '处理中...' : '批准' }}
          </button>
          <button
            v-if="version.status === 'pending'"
            class="btn btn-danger btn-sm"
            :disabled="processingIds.has(version.id)"
            :aria-label="`驳回 ${version.platform} 版本`"
            @click="rejectVersion(version.id)"
          >
            {{ processingIds.has(version.id) ? '处理中...' : '驳回' }}
          </button>
        </div>
      </div>
    </div>

    <div v-else class="versions-empty">暂无版本信息</div>
  </div>
</template>

<style scoped>
.versions-section { margin-top: var(--space-lg); border-top: 1px solid var(--divider); padding-top: var(--space-lg); }
.versions-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-md); }
.versions-title { font-size: var(--text-md); font-weight: 600; color: var(--text-primary); }
.versions-list { display: flex; flex-direction: column; gap: var(--space-sm); }

.version-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md);
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--border-color);
}
.version-item.version-pending { border-left-color: var(--warning); }
.version-item.version-approved { border-left-color: var(--success); }
.version-item.version-rejected { border-left-color: var(--danger); }

.version-info { display: flex; align-items: center; gap: var(--space-md); }
.version-platform { font-weight: 600; color: var(--text-primary); text-transform: capitalize; }
.version-status { font-size: var(--text-sm); color: var(--text-secondary); padding: var(--space-xs) var(--space-sm); background: var(--bg-card); border-radius: var(--radius-full); }
.version-score { font-size: var(--text-sm); color: var(--text-tertiary); }
.version-actions { display: flex; gap: var(--space-sm); }
.versions-loading,
.versions-empty { padding: var(--space-md); text-align: center; color: var(--text-tertiary); font-size: var(--text-sm); }
</style>
