<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { useToast } from '../composables/useToast'
import { marked } from 'marked'
import SkeletonLoader from '../components/SkeletonLoader.vue'

const store = useDashboardStore()
const toast = useToast()
const selectedId = ref<string | null>(null)
const rejectReason = ref('')
const showRejectInput = ref<string | null>(null)
const showApproveConfirm = ref<string | null>(null)

// Version-level operations
interface PlatformVersion {
  id: number
  session_id: number
  platform: string
  status: string
  score: number | null
  content_path: string | null
}

const sessionVersions = ref<PlatformVersion[]>([])
const versionsLoading = ref(false)
const versionProcessingIds = ref<Set<number>>(new Set())

// Batch operations
const selectedIds = ref<Set<string>>(new Set())
const isBatchMode = ref(false)
const batchProcessing = ref(false)

// Track loading state per article
const processingIds = ref<Set<string>>(new Set())

// Markdown rendering
const renderedContent = computed(() => {
  const article = store.approvalQueue.find(a => a.id === selectedId.value)
  if (!article?.content_preview) return ''
  return marked(article.content_preview) as string
})

async function fetchVersions(sessionId: number) {
  versionsLoading.value = true
  try {
    const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
    const res = await fetch(`${API_BASE}/api/approval/versions/${sessionId}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    sessionVersions.value = data.versions || []
  } catch (e) {
    toast.error(`获取版本列表失败: ${e instanceof Error ? e.message : '未知错误'}`)
    sessionVersions.value = []
  } finally {
    versionsLoading.value = false
  }
}

async function approveVersion(versionId: number) {
  versionProcessingIds.value.add(versionId)
  try {
    const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
    const res = await fetch(`${API_BASE}/api/approval/version/${versionId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    toast.success('版本已批准')
    // Refresh versions list
    const version = sessionVersions.value.find(v => v.id === versionId)
    if (version) {
      version.status = 'approved'
    }
  } catch (e) {
    toast.error(`批准失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    versionProcessingIds.value.delete(versionId)
  }
}

async function rejectVersion(versionId: number) {
  versionProcessingIds.value.add(versionId)
  try {
    const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
    const res = await fetch(`${API_BASE}/api/approval/version/${versionId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    toast.success('版本已驳回')
    const version = sessionVersions.value.find(v => v.id === versionId)
    if (version) {
      version.status = 'rejected'
    }
  } catch (e) {
    toast.error(`驳回失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    versionProcessingIds.value.delete(versionId)
  }
}

const selectedCount = computed(() => selectedIds.value.size)
const allSelected = computed(() =>
  store.approvalQueue.length > 0 && selectedIds.value.size === store.approvalQueue.length
)

function select(id: string) {
  if (isBatchMode.value) {
    toggleSelection(id)
  } else {
    selectedId.value = selectedId.value === id ? null : id
  }
}

function toggleSelection(id: string) {
  const newSet = new Set(selectedIds.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  selectedIds.value = newSet
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(store.approvalQueue.map(a => a.id))
  }
}

function toggleBatchMode() {
  isBatchMode.value = !isBatchMode.value
  if (!isBatchMode.value) {
    selectedIds.value = new Set()
  }
}

async function batchApprove() {
  if (selectedIds.value.size === 0) return
  batchProcessing.value = true
  try {
    for (const id of selectedIds.value) {
      await store.approve(id)
    }
    selectedIds.value = new Set()
    isBatchMode.value = false
  } finally {
    batchProcessing.value = false
  }
}

async function doReject(id: string) {
  if (!rejectReason.value.trim()) return
  processingIds.value.add(id)
  try {
    await store.reject(id, rejectReason.value)
    showRejectInput.value = null
    rejectReason.value = ''
  } finally {
    processingIds.value.delete(id)
  }
}

function cancelReject() {
  showRejectInput.value = null
  rejectReason.value = ''
}

async function confirmApprove(id: string) {
  processingIds.value.add(id)
  try {
    await store.approve(id)
    showApproveConfirm.value = null
  } finally {
    processingIds.value.delete(id)
  }
}

function cancelApprove() {
  showApproveConfirm.value = null
}

const pendingCount = computed(() => store.approvalQueue.length)

// Keyboard shortcuts
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    selectedId.value = null
    showRejectInput.value = null
    showApproveConfirm.value = null
    if (isBatchMode.value) toggleBatchMode()
  }
  if (e.key === 'a' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault()
    if (!isBatchMode.value) toggleBatchMode()
    toggleSelectAll()
  }
}

// Register keyboard handler
import { onMounted, onUnmounted } from 'vue'
onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})
onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div class="approval-view">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title">审批队列</h2>
        <p class="page-subtitle">审核并发布内容到各平台</p>
      </div>
      <div class="page-actions">
        <button
          v-if="pendingCount > 0"
          class="btn btn-ghost btn-sm"
          :class="{ 'active': isBatchMode }"
          @click="toggleBatchMode"
        >
          {{ isBatchMode ? '取消批量' : '批量操作' }}
        </button>
        <span class="stat-badge" :class="{ 'has-items': pendingCount > 0 }">
          {{ pendingCount }} 篇待审
        </span>
      </div>
    </div>

    <!-- Batch Actions Bar -->
    <transition name="slide">
      <div v-if="isBatchMode && pendingCount > 0" class="batch-bar">
        <div class="batch-left">
          <label class="batch-checkbox">
            <input
              type="checkbox"
              :checked="allSelected"
              @change="toggleSelectAll"
            >
            <span>全选</span>
          </label>
          <span class="batch-count">已选 {{ selectedCount }} 篇</span>
        </div>
        <div class="batch-right">
          <button
            class="btn btn-success btn-sm"
            :disabled="selectedCount === 0 || batchProcessing"
            @click="batchApprove"
          >
            <span v-if="batchProcessing" class="loading-spinner-sm"></span>
            {{ batchProcessing ? '处理中...' : `批量通过 (${selectedCount})` }}
          </button>
        </div>
      </div>
    </transition>

    <!-- Loading Skeletons -->
    <div v-if="store.isLoading('approval') && store.approvalQueue.length === 0" class="articles-skeleton">
      <div v-for="i in 3" :key="i" class="card article-card-skeleton" style="padding: 20px;">
        <SkeletonLoader type="title" width="70%" />
        <SkeletonLoader type="text" :count="3" />
        <div style="display: flex; gap: 8px; margin-top: 12px;">
          <SkeletonLoader type="button" />
          <SkeletonLoader type="button" />
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="store.approvalQueue.length === 0" class="card empty-state">
      <div class="empty-state-icon">✅</div>
      <div class="empty-state-title">暂无待审批文章</div>
      <div class="empty-state-description">
        所有文章已审批完毕，等待下一轮 Writer 生产
      </div>
    </div>

    <!-- Article List -->
    <div
      v-for="article in store.approvalQueue"
      :key="article.id"
      class="card article-card"
      :class="{ 'selected': isBatchMode && selectedIds.has(article.id) }"
    >
      <!-- Batch Checkbox -->
      <div v-if="isBatchMode" class="batch-select" @click.stop="toggleSelection(article.id)">
        <input
          type="checkbox"
          :checked="selectedIds.has(article.id)"
          @click.stop
          @change="toggleSelection(article.id)"
        >
      </div>

      <!-- Article Header -->
      <div class="article-header" @click="select(article.id)">
        <div class="article-info">
          <h3 class="article-title">{{ article.meta.topic || '未知选题' }}</h3>
          <div class="article-meta">
            <span class="meta-item">
              <span class="meta-icon">📊</span>
              评分 {{ article.meta.proofread_score || '-' }}
            </span>
            <span class="meta-divider">·</span>
            <span class="meta-item">
              <span class="meta-icon">🔄</span>
              修订 {{ article.meta.revised_rounds || 0 }} 轮
            </span>
            <span class="meta-divider">·</span>
            <span class="meta-item">
              <span class="meta-icon">📝</span>
              {{ article.meta.word_count || 0 }} 字
            </span>
          </div>
        </div>
        <div class="article-actions">
          <template v-if="showApproveConfirm === article.id">
            <button 
              class="btn btn-success btn-sm" 
              :disabled="processingIds.has(article.id)"
              @click.stop="confirmApprove(article.id)"
            >
              <span v-if="processingIds.has(article.id)" class="loading-spinner-sm"></span>
              {{ processingIds.has(article.id) ? '处理中...' : '确认通过' }}
            </button>
            <button 
              class="btn btn-ghost btn-sm" 
              :disabled="processingIds.has(article.id)"
              @click.stop="cancelApprove"
            >
              取消
            </button>
          </template>
          <button 
            v-else
            class="btn btn-success btn-sm" 
            :disabled="processingIds.has(article.id)"
            @click.stop="showApproveConfirm = article.id"
          >
            ✅ 通过
          </button>
          <button 
            v-if="showRejectInput !== article.id" 
            class="btn btn-danger btn-sm"
            :disabled="processingIds.has(article.id)"
            @click.stop="showRejectInput = article.id"
          >
            ❌ 驳回
          </button>
        </div>
      </div>

      <!-- Reject Input -->
      <transition name="slide">
        <div v-if="showRejectInput === article.id" class="reject-form">
          <div class="reject-input-group">
            <input 
              v-model="rejectReason" 
              class="input reject-input"
              placeholder="请输入驳回原因..." 
              :disabled="processingIds.has(article.id)"
              @keyup.enter="doReject(article.id)"
            >
            <button 
              class="btn btn-danger" 
              :disabled="!rejectReason.trim() || processingIds.has(article.id)"
              @click="doReject(article.id)"
            >
              <span v-if="processingIds.has(article.id)" class="loading-spinner-sm"></span>
              {{ processingIds.has(article.id) ? '处理中...' : '确认驳回' }}
            </button>
            <button 
              class="btn btn-ghost" 
              :disabled="processingIds.has(article.id)"
              @click="cancelReject"
            >
              取消
            </button>
          </div>
        </div>
      </transition>

      <!-- Content Preview (expandable) -->
      <transition name="slide">
        <div v-if="selectedId === article.id" class="article-preview">
          <div class="preview-header">
            <span class="preview-label">文章预览</span>
            <span class="preview-hint">点击收起</span>
          </div>
          <div class="preview-content">
            <div v-if="article.meta.topic" class="preview-title">
              # {{ article.meta.topic }}
            </div>
            <div class="preview-text markdown-body" v-html="renderedContent"></div>
          </div>

          <!-- Version-level operations for database-tracked articles -->
          <div v-if="article.source === 'database' && article.db_version_id" class="versions-section">
            <div class="versions-header">
              <span class="versions-title">平台版本管理</span>
              <button
                class="btn btn-ghost btn-sm"
                :disabled="versionsLoading"
                @click.stop="fetchVersions(article.db_version_id)"
              >
                {{ versionsLoading ? '加载中...' : '刷新版本' }}
              </button>
            </div>
            <div v-if="versionsLoading" class="versions-loading">
              <SkeletonLoader type="text" :count="2" />
            </div>
            <div v-else-if="sessionVersions.length > 0" class="versions-list">
              <div
                v-for="version in sessionVersions"
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
                    :disabled="versionProcessingIds.has(version.id)"
                    @click.stop="approveVersion(version.id)"
                  >
                    {{ versionProcessingIds.has(version.id) ? '处理中...' : '批准' }}
                  </button>
                  <button
                    v-if="version.status === 'pending'"
                    class="btn btn-danger btn-sm"
                    :disabled="versionProcessingIds.has(version.id)"
                    @click.stop="rejectVersion(version.id)"
                  >
                    {{ versionProcessingIds.has(version.id) ? '处理中...' : '驳回' }}
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="versions-empty">
              暂无版本信息
            </div>
          </div>
        </div>
      </transition>

      <!-- Expand Hint -->
      <div v-if="selectedId !== article.id" class="expand-hint" @click="select(article.id)">
        <span class="expand-icon">👁️</span>
        <span>点击预览文章内容</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.approval-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

/* ── Page Actions ────────────────────────────────────────────── */
.page-actions {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.page-actions .btn.active {
  background: var(--primary-light);
  color: var(--primary);
  border-color: var(--primary);
}

/* ── Batch Bar ───────────────────────────────────────────────── */
.batch-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-lg);
  background: var(--primary-light);
  border-radius: var(--radius-lg);
  border: 1px solid var(--primary);
}

.batch-left {
  display: flex;
  align-items: center;
  gap: var(--space-lg);
}

.batch-checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text-primary);
}

.batch-checkbox input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.batch-count {
  font-size: var(--text-sm);
  color: var(--primary);
  font-weight: 500;
}

.batch-right {
  display: flex;
  gap: var(--space-sm);
}

/* ── Batch Select ────────────────────────────────────────────── */
.batch-select {
  position: absolute;
  top: var(--space-md);
  left: var(--space-md);
  z-index: 10;
}

.batch-select input[type="checkbox"] {
  width: 20px;
  height: 20px;
  cursor: pointer;
}

.article-card.selected {
  border-color: var(--primary);
  background: var(--primary-light);
}

/* ── Page Header ─────────────────────────────────────────────── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-xs) 0;
}

.page-subtitle {
  font-size: var(--text-md);
  color: var(--text-tertiary);
  margin: 0;
}

.page-stats {
  display: flex;
  align-items: center;
}

.stat-badge {
  padding: var(--space-sm) var(--space-lg);
  background: var(--bg-hover);
  color: var(--text-secondary);
  font-size: var(--text-md);
  font-weight: 500;
  border-radius: var(--radius-full);
}

.stat-badge.has-items {
  background: var(--primary-light);
  color: var(--primary);
}

/* ── Article Card ────────────────────────────────────────────── */
.article-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  transition: all var(--transition-normal);
  position: relative;
}

.article-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}

.article-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  cursor: pointer;
  gap: var(--space-lg);
}

.article-info {
  flex: 1;
  min-width: 0;
}

.article-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-sm) 0;
  line-height: 1.4;
}

.article-meta {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.meta-icon {
  font-size: var(--text-md);
}

.meta-divider {
  color: var(--text-disabled);
}

.article-actions {
  display: flex;
  gap: var(--space-sm);
  flex-shrink: 0;
}

/* ── Reject Form ─────────────────────────────────────────────── */
.reject-form {
  padding-top: var(--space-md);
  border-top: 1px solid var(--divider);
}

.reject-input-group {
  display: flex;
  gap: var(--space-sm);
}

.reject-input {
  flex: 1;
}

/* ── Article Preview ─────────────────────────────────────────── */
.article-preview {
  border-top: 1px solid var(--divider);
  padding-top: var(--space-md);
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-md);
}

.preview-label {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.preview-hint {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.preview-content {
  background: var(--bg-hover);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  max-height: 400px;
  overflow-y: auto;
}

.preview-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-md);
  padding-bottom: var(--space-md);
  border-bottom: 1px solid var(--divider);
}

.preview-text {
  font-size: var(--text-md);
  color: var(--text-secondary);
  line-height: 1.8;
  word-break: break-word;
}

/* Markdown styles */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin-top: var(--space-lg);
  margin-bottom: var(--space-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.markdown-body :deep(p) {
  margin-bottom: var(--space-md);
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin-bottom: var(--space-md);
  padding-left: var(--space-xl);
}

.markdown-body :deep(li) {
  margin-bottom: var(--space-xs);
}

.markdown-body :deep(code) {
  background: var(--bg-active);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 0.9em;
}

.markdown-body :deep(pre) {
  background: var(--bg-active);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  overflow-x: auto;
  margin-bottom: var(--space-md);
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--primary);
  padding-left: var(--space-md);
  color: var(--text-tertiary);
  margin-bottom: var(--space-md);
}

.markdown-body :deep(a) {
  color: var(--primary);
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(strong) {
  font-weight: 600;
  color: var(--text-primary);
}

.markdown-body :deep(em) {
  font-style: italic;
}

/* ── Expand Hint ─────────────────────────────────────────────── */
.expand-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.expand-hint:hover {
  background: var(--primary-light);
  color: var(--primary);
}

.expand-icon {
  font-size: var(--text-md);
}

/* ── Versions Section ────────────────────────────────────────── */
.versions-section {
  margin-top: var(--space-lg);
  border-top: 1px solid var(--divider);
  padding-top: var(--space-lg);
}

.versions-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-md);
}

.versions-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
}

.versions-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.version-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md);
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--border-color);
}

.version-item.version-pending {
  border-left-color: var(--warning);
}

.version-item.version-approved {
  border-left-color: var(--success);
}

.version-item.version-rejected {
  border-left-color: var(--danger);
}

.version-info {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.version-platform {
  font-weight: 600;
  color: var(--text-primary);
  text-transform: capitalize;
}

.version-status {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  padding: var(--space-xs) var(--space-sm);
  background: var(--bg-card);
  border-radius: var(--radius-full);
}

.version-score {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

.version-actions {
  display: flex;
  gap: var(--space-sm);
}

.versions-loading,
.versions-empty {
  padding: var(--space-md);
  text-align: center;
  color: var(--text-tertiary);
  font-size: var(--text-sm);
}

/* ── Loading Spinner ─────────────────────────────────────────── */
.loading-spinner-sm {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: var(--space-xs);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Empty State ─────────────────────────────────────────────── */
.empty-state {
  padding: var(--space-4xl);
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .article-header {
    flex-direction: column;
    gap: var(--space-md);
  }
  
  .article-actions {
    width: 100%;
  }
  
  .article-actions .btn {
    flex: 1;
  }
  
  .reject-input-group {
    flex-direction: column;
  }
}
</style>
