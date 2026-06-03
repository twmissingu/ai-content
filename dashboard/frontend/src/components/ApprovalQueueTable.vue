<script setup lang="ts">
/**
 * ApprovalQueueTable — article list with batch operations, inline editing, rejection, preview.
 * Extracted from ApprovalView.vue to reduce its size.
 * Uses ApprovalVersionPanel and ApprovalPublishPanel for sub-sections.
 *
 * The parent (ApprovalView) manages keyboard shortcuts and pagination;
 * this component handles per-article UI state.
 */
import { ref, computed, watch, nextTick } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { useToast } from '../composables/useToast'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import SkeletonLoader from './SkeletonLoader.vue'
import ImageGallery from './ImageGallery.vue'
import ApprovalVersionPanel from './ApprovalVersionPanel.vue'
import ApprovalPublishPanel from './ApprovalPublishPanel.vue'

const store = useDashboardStore()
const toast = useToast()

// ── Props for batch mode (controlled by parent) ─────────────────────
const props = defineProps<{
  articles: any[]
  isBatchMode: boolean
  selectedIds: Set<string>
  allSelected: boolean
  selectedCount: number
}>()

const emit = defineEmits<{
  select: [id: string | null]
  'toggle-selection': [id: string]
  'toggle-select-all': []
  'batch-approve': []
  'start-edit': [id: string]
  'save-edit': [id: string, content: string]
  'cancel-edit': []
  'escape-batch-mode': []
  refresh: []
}>()

// ── Per-article UI state (local, not shared with parent) ────────────
const selectedId = ref<string | null>(null)
const rejectReason = ref('')
const showRejectInput = ref<string | null>(null)
const showApproveConfirm = ref<string | null>(null)
const processingIds = ref<Set<string>>(new Set())

// Inline editing
const isEditing = ref(false)
const editContent = ref('')
const editSaving = ref(false)

const editPreview = computed(() => {
  if (!editContent.value) return ''
  return DOMPurify.sanitize(marked(editContent.value) as string)
})

// Markdown rendering for selected article preview
const renderedContent = computed(() => {
  const article = props.articles.find(a => a.id === selectedId.value)
  if (!article?.content_preview) return ''
  return DOMPurify.sanitize(marked(article.content_preview) as string)
})

// Rejection presets
const rejectPresets = [
  'AI腔太重，需要重写',
  '论据不足，缺乏数据支撑',
  '标题不够吸引人',
  '内容与选题不符',
  '需要补充案例',
]

// ── Selection logic ───────────────────────────────────────────────────
function select(id: string) {
  if (props.isBatchMode) {
    emit('toggle-selection', id)
  } else {
    selectedId.value = selectedId.value === id ? null : id
  }
}

// ── Actions ───────────────────────────────────────────────────────────
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

// ── Inline editing ────────────────────────────────────────────────────
async function startEditing(articleId: string) {
  const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
  try {
    const res = await fetch(`${API_BASE}/api/approval/article/${articleId}/content`)
    if (!res.ok) throw new Error('Failed to fetch content')
    const data = await res.json()
    editContent.value = data.content
    isEditing.value = true
  } catch (e) {
    toast.error('加载文章内容失败')
  }
}

function cancelEditing() {
  isEditing.value = false
  editContent.value = ''
}

async function saveEditing(articleId: string) {
  editSaving.value = true
  const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
  try {
    const res = await fetch(`${API_BASE}/api/approval/article/${articleId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: editContent.value }),
    })
    if (!res.ok) throw new Error('Failed to save')
    isEditing.value = false
    editContent.value = ''
    toast.success('文章已保存')
    emit('refresh')
  } catch (e) {
    toast.error('保存失败')
  } finally {
    editSaving.value = false
  }
}

// ── Focus management ──────────────────────────────────────────────────
watch(showRejectInput, async (id) => {
  if (id) {
    await nextTick()
    const input = document.querySelector('.reject-input') as HTMLInputElement
    input?.focus()
  }
})

watch(showApproveConfirm, async (id) => {
  if (id) {
    await nextTick()
    const btn = document.querySelector('.article-actions .btn-success') as HTMLButtonElement
    btn?.focus()
  }
})

// ── Keyboard shortcut helpers (called from parent's document listener) ─
function handleEscape() {
  if (showRejectInput.value || showApproveConfirm.value) {
    showRejectInput.value = null
    showApproveConfirm.value = null
    rejectReason.value = ''
    return
  }
  if (selectedId.value) {
    selectedId.value = null
    return
  }
  emit('escape-batch-mode')
}

function handleKeyAction(e: KeyboardEvent) {
  if (e.key === 'Enter' && selectedId.value && !showRejectInput.value && !showApproveConfirm.value) {
    e.preventDefault()
    showApproveConfirm.value = selectedId.value
    return
  }
  if ((e.key === 'r' || e.key === 'R') && selectedId.value && !showRejectInput.value && !showApproveConfirm.value) {
    e.preventDefault()
    showRejectInput.value = selectedId.value
    return
  }
}

// ── Public API for parent (keyboard shortcuts) ───────────────────────
defineExpose({
  handleEscape,
  handleKeyAction,
})
</script>

<template>
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
  <div v-else-if="articles.length === 0" class="card empty-state">
    <div class="empty-state-icon">✅</div>
    <div class="empty-state-title">暂无待审批文章</div>
    <div class="empty-state-description">
      所有文章已审批完毕，等待下一轮 Writer 生产
    </div>
    <router-link to="/pipeline" class="btn btn-primary" aria-label="查看管线状态">
      📊 查看管线状态
    </router-link>
  </div>

  <!-- Article List -->
  <div
    v-for="article in articles"
    :key="article.id"
    class="card article-card"
    :class="{ 'selected': isBatchMode && selectedIds.has(article.id) }"
  >
    <!-- Batch Checkbox -->
    <div v-if="isBatchMode" class="batch-select" @click.stop="emit('toggle-selection', article.id)">
      <input
        type="checkbox"
        :checked="selectedIds.has(article.id)"
        :aria-label="`选择 ${article.meta.topic || '未知选题'}`"
        @click.stop
        @change="emit('toggle-selection', article.id)"
      >
    </div>

    <!-- Article Header -->
    <div
      class="article-header"
      role="button"
      tabindex="0"
      :aria-label="`${article.meta.topic || '未知选题'} — 点击预览`"
      @click="select(article.id)"
      @keydown.enter="select(article.id)"
      @keydown.space.prevent="select(article.id)"
    >
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
          <span v-if="article.meta.platform" class="meta-divider">·</span>
          <span v-if="article.meta.platform" class="meta-item platform-tag">
            <span class="meta-icon">📱</span>
            {{ article.meta.platform }}
          </span>
        </div>
      </div>
      <div class="article-actions">
        <template v-if="showApproveConfirm === article.id">
          <button
            class="btn btn-success btn-sm"
            :disabled="processingIds.has(article.id)"
            aria-label="确认通过"
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
          aria-label="通过文章"
          @click.stop="showApproveConfirm = article.id"
        >
          ✅ 通过
        </button>
        <button
          v-if="showRejectInput !== article.id"
          class="btn btn-danger btn-sm"
          :disabled="processingIds.has(article.id)"
          aria-label="驳回文章"
          @click.stop="showRejectInput = article.id"
        >
          ❌ 驳回
        </button>
        <button
          v-if="showRejectInput !== article.id && !isEditing"
          class="btn btn-ghost btn-sm"
          aria-label="编辑文章"
          @click.stop="startEditing(article.id)"
        >
          ✏️ 编辑
        </button>
      </div>
    </div>

    <!-- Reject Input -->
    <transition name="slide">
      <div v-if="showRejectInput === article.id" class="reject-form">
        <div class="reject-presets">
          <button
            v-for="preset in rejectPresets"
            :key="preset"
            class="btn btn-ghost btn-xs preset-btn"
            :aria-label="`预设原因: ${preset}`"
            @click.stop="rejectReason = preset"
          >
            {{ preset }}
          </button>
        </div>
        <div class="reject-input-group">
          <input
            v-model="rejectReason"
            class="input reject-input"
            placeholder="请输入驳回原因..."
            :disabled="processingIds.has(article.id)"
            :aria-label="`驳回原因 — ${article.meta.topic || article.id}`"
            @keyup.enter="doReject(article.id)"
          >
          <button
            class="btn btn-danger"
            :disabled="!rejectReason.trim() || processingIds.has(article.id)"
            aria-label="确认驳回"
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
        <!-- Editor Mode -->
        <div v-if="isEditing" class="editor-section">
          <div class="editor-header">
            <span class="preview-label">编辑文章</span>
            <div class="editor-actions">
              <button class="btn btn-ghost btn-sm" @click="cancelEditing">取消</button>
              <button
                class="btn btn-primary btn-sm"
                :disabled="editSaving"
                @click="saveEditing(article.id)"
              >
                {{ editSaving ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
          <div class="editor-body">
            <textarea
              v-model="editContent"
              class="editor-textarea"
              spellcheck="false"
              aria-label="文章编辑内容"
            ></textarea>
            <div class="editor-preview markdown-body" v-html="editPreview"></div>
          </div>
        </div>

        <!-- Read-only Preview -->
        <template v-else>
          <div class="preview-header">
            <span class="preview-label">文章预览</span>
            <span class="preview-hint">点击收起</span>
          </div>
          <div class="preview-content">
            <div v-if="article.meta.topic" class="preview-title"># {{ article.meta.topic }}</div>
            <div class="preview-text markdown-body" v-html="renderedContent"></div>
          </div>

          <!-- Image Gallery -->
          <div class="preview-images">
            <span class="preview-label">配图</span>
            <ImageGallery :images="article.meta.images || []" />
          </div>

          <!-- Publish -->
          <ApprovalPublishPanel
            :article-id="article.id"
            :disabled="processingIds.has(article.id)"
            @published="emit('refresh')"
          />
        </template>

        <!-- Version-level operations -->
        <ApprovalVersionPanel
          v-if="article.source === 'database' && article.db_version_id"
          :session-id="article.db_version_id"
        />
      </div>
    </transition>

    <!-- Expand Hint -->
    <div
      v-if="selectedId !== article.id"
      class="expand-hint"
      role="button"
      tabindex="0"
      :aria-label="`预览文章 — ${article.meta.topic || article.id}`"
      @click="select(article.id)"
      @keydown.enter="select(article.id)"
      @keydown.space.prevent="select(article.id)"
    >
      <span class="expand-icon">👁️</span>
      <span>点击预览文章内容</span>
    </div>
  </div>
</template>

<style scoped>
/* ── Article Card ────────────────────────────────────────────── */
.article-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  transition: all var(--transition-normal);
  position: relative;
}
.article-card:hover { box-shadow: var(--shadow-lg); transform: translateY(-2px); }
.article-card.selected { border-color: var(--primary); background: var(--primary-light); }

.article-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  cursor: pointer;
  gap: var(--space-lg);
}

.article-info { flex: 1; min-width: 0; }

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

.meta-icon { font-size: var(--text-md); }
.meta-divider { color: var(--text-disabled); }

.platform-tag {
  background: var(--primary-light);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  color: var(--primary);
}

.platform-tag .meta-icon { font-size: var(--text-sm); }

.article-actions {
  display: flex;
  gap: var(--space-sm);
  flex-shrink: 0;
}

/* ── Batch Select ───────────────────────────────────────────── */
.batch-select {
  position: absolute;
  top: var(--space-md);
  left: var(--space-md);
  z-index: 10;
  padding: var(--space-xs);
}

.batch-select input[type="checkbox"] {
  width: 20px;
  height: 20px;
  cursor: pointer;
}

/* ── Reject Form ────────────────────────────────────────────── */
.reject-form {
  padding-top: var(--space-md);
  border-top: 1px solid var(--divider);
}

.reject-presets {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  margin-bottom: var(--space-sm);
}

.preset-btn {
  font-size: var(--text-xs);
  padding: var(--space-xs) var(--space-sm);
  min-height: 28px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  white-space: nowrap;
}

.preset-btn:hover {
  background: var(--danger-light);
  border-color: var(--danger);
  color: var(--danger);
}

.reject-input-group { display: flex; gap: var(--space-sm); }
.reject-input { flex: 1; }

/* ── Article Preview ────────────────────────────────────────── */
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

.preview-label { font-size: var(--text-sm); font-weight: 600; color: var(--text-primary); }
.preview-hint { font-size: var(--text-xs); color: var(--text-tertiary); }

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

/* ── Image Gallery ──────────────────────────────────────────── */
.preview-images {
  margin-top: var(--space-md);
  padding-top: var(--space-md);
  border-top: 1px solid var(--divider);
}

/* ── Markdown styles ────────────────────────────────────────── */
:deep(.markdown-body h1),
:deep(.markdown-body h2),
:deep(.markdown-body h3) {
  margin-top: var(--space-lg);
  margin-bottom: var(--space-sm);
  font-weight: 600;
  color: var(--text-primary);
}
:deep(.markdown-body p) { margin-bottom: var(--space-md); }
:deep(.markdown-body ul),
:deep(.markdown-body ol) { margin-bottom: var(--space-md); padding-left: var(--space-xl); }
:deep(.markdown-body li) { margin-bottom: var(--space-xs); }
:deep(.markdown-body code) { background: var(--bg-active); padding: 2px 6px; border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: 0.9em; }
:deep(.markdown-body pre) { background: var(--bg-active); padding: var(--space-md); border-radius: var(--radius-md); overflow-x: auto; margin-bottom: var(--space-md); }
:deep(.markdown-body blockquote) { border-left: 3px solid var(--primary); padding-left: var(--space-md); color: var(--text-tertiary); margin-bottom: var(--space-md); }
:deep(.markdown-body a) { color: var(--primary); text-decoration: none; }
:deep(.markdown-body a:hover) { text-decoration: underline; }
:deep(.markdown-body strong) { font-weight: 600; color: var(--text-primary); }
:deep(.markdown-body em) { font-style: italic; }

/* ── Expand Hint ────────────────────────────────────────────── */
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

.expand-icon { font-size: var(--text-md); }

/* ── Inline Editor ──────────────────────────────────────────── */
.editor-section {
  margin-top: var(--space-md);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.editor-actions { display: flex; gap: var(--space-xs); }

.editor-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 400px;
}

.editor-textarea {
  width: 100%;
  height: 100%;
  min-height: 400px;
  padding: var(--space-md);
  border: none;
  border-right: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.6;
  resize: vertical;
  outline: none;
}

.editor-textarea:focus { background: var(--bg-primary); }

.editor-preview {
  padding: var(--space-md);
  overflow-y: auto;
  background: var(--bg-card);
}

/* ── Loading Spinner ────────────────────────────────────────── */
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

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Empty State ────────────────────────────────────────────── */
.empty-state {
  padding: var(--space-4xl);
  text-align: center;
}
.empty-state .btn { margin-top: var(--space-lg); }
.empty-state-icon { font-size: 48px; margin-bottom: var(--space-lg); }
.empty-state-title { font-size: var(--text-2xl); font-weight: 600; color: var(--text-primary); margin-bottom: var(--space-sm); }
.empty-state-description { font-size: var(--text-md); color: var(--text-tertiary); margin-bottom: var(--space-xl); }

/* ── Responsive ─────────────────────────────────────────────── */
@media (max-width: 768px) {
  .article-header { flex-direction: column; gap: var(--space-md); }
  .article-actions { width: 100%; }
  .article-actions .btn { flex: 1; }
  .reject-input-group { flex-direction: column; }
  .editor-body { grid-template-columns: 1fr; }
  .editor-textarea { border-right: none; border-bottom: 1px solid var(--border-color); min-height: 200px; }
}
</style>
