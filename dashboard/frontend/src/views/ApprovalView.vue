<script setup lang="ts">
/**
 * ApprovalView.vue — slim layout coordinator for the approval page.
 * Extracted sub-components:
 *   - ApprovalQueueTable (article list, inline editing, reject forms, version panel, publish)
 *   - ApprovalVersionPanel (platform version management)
 *   - ApprovalPublishPanel (publish button)
 */
import { ref, computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { useToast } from '../composables/useToast'
import { useKeyboardShortcut, isInputElement } from '../composables/useKeyboardShortcut'
import PaginationBar from '../components/PaginationBar.vue'
import ApprovalQueueTable from '../components/ApprovalQueueTable.vue'

const store = useDashboardStore()
const toast = useToast()

// ── Batch mode (page-level state shared with ApprovalQueueTable) ────
const isBatchMode = ref(false)
const selectedIds = ref<Set<string>>(new Set())
const batchProcessing = ref(false)

const allSelected = computed(() =>
  store.approvalQueue.length > 0 && selectedIds.value.size === store.approvalQueue.length
)
const selectedCount = computed(() => selectedIds.value.size)

function toggleBatchMode() {
  isBatchMode.value = !isBatchMode.value
  if (!isBatchMode.value) selectedIds.value = new Set()
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(store.approvalQueue.map(a => a.id))
  }
}

function handleToggleSelection(id: string) {
  const s = new Set(selectedIds.value)
  if (s.has(id)) { s.delete(id) } else { s.add(id) }
  selectedIds.value = s
}

async function batchApprove() {
  if (selectedIds.value.size === 0) return
  batchProcessing.value = true
  try {
    const results = await Promise.allSettled([...selectedIds.value].map(id => store.approve(id)))
    const rejected = results.filter(r => r.status === 'rejected')
    if (rejected.length > 0) {
      toast.warning(`${rejected.length} 篇审批失败，${selectedIds.value.size - rejected.length} 篇已通过`)
    }
    selectedIds.value = new Set()
    isBatchMode.value = false
  } finally {
    batchProcessing.value = false
  }
}

// ── Pagination ──────────────────────────────────────────────────────
const currentPage = ref(1)
const pageSize = 10
const paginatedArticles = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return store.approvalQueue.slice(start, start + pageSize)
})

// ── Keyboard shortcuts ──────────────────────────────────────────────
const tableRef = ref<InstanceType<typeof ApprovalQueueTable> | null>(null)

function handleKeydown(e: KeyboardEvent) {
  if (isInputElement(e.target)) return

  // Escape: clear batch mode or delegate to table
  if (e.key === 'Escape') {
    if (isBatchMode.value) {
      toggleBatchMode()
      return
    }
    tableRef.value?.handleEscape()
    return
  }

  // Ctrl+A: select all (page-level)
  if ((e.key === 'a' || e.key === 'A') && (e.metaKey || e.ctrlKey)) {
    e.preventDefault()
    if (!isBatchMode.value) toggleBatchMode()
    toggleSelectAll()
    return
  }

  // Delegate Enter/R to table (article-level shortcuts)
  if (e.key === 'Enter' || e.key === 'r' || e.key === 'R') {
    tableRef.value?.handleKeyAction(e)
  }
}

useKeyboardShortcut(handleKeydown)
</script>

<template>
  <div class="approval-view">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title" id="approval-title">审批队列</h2>
        <p class="page-subtitle">审核并发布内容到各平台</p>
      </div>
      <div class="page-actions">
        <button
          v-if="store.pendingCount > 0"
          class="btn btn-ghost btn-sm"
          :class="{ active: isBatchMode }"
          :aria-label="isBatchMode ? '取消批量操作' : '批量操作'"
          :aria-pressed="isBatchMode"
          @click="toggleBatchMode"
        >
          {{ isBatchMode ? '取消批量' : '批量操作' }}
        </button>
        <span class="stat-badge" :class="{ 'has-items': store.pendingCount > 0 }" role="status" aria-live="polite">
          {{ store.pendingCount }} 篇待审
        </span>
      </div>
    </div>

    <!-- Batch Actions Bar -->
    <transition name="slide">
      <div v-if="isBatchMode && store.pendingCount > 0" class="batch-bar" role="region" aria-label="批量操作">
        <div class="batch-left">
          <label class="batch-checkbox">
            <input
              type="checkbox"
              :checked="allSelected"
              aria-label="全选所有文章"
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
            :aria-label="`批量通过 ${selectedCount} 篇文章`"
            @click="batchApprove"
          >
            <span v-if="batchProcessing" class="loading-spinner-sm"></span>
            {{ batchProcessing ? '处理中...' : `批量通过 (${selectedCount})` }}
          </button>
        </div>
      </div>
    </transition>

    <!-- Article List (via ApprovalQueueTable) -->
    <ApprovalQueueTable
      ref="tableRef"
      :articles="paginatedArticles"
      :is-batch-mode="isBatchMode"
      :selected-ids="selectedIds"
      :all-selected="allSelected"
      :selected-count="selectedCount"
      @toggle-selection="handleToggleSelection"
      @toggle-select-all="toggleSelectAll"
      @escape-batch-mode="toggleBatchMode"
      @refresh="store.fetchApprovalQueue()"
    />

    <!-- Pagination -->
    <PaginationBar
      v-if="store.approvalQueue.length > pageSize"
      :total="store.approvalQueue.length"
      :page-size="pageSize"
      :current-page="currentPage"
      @update:currentPage="currentPage = $event"
    />

    <!-- Keyboard Shortcuts Hint -->
    <div v-if="store.approvalQueue.length > 0" class="keyboard-hints" role="region" aria-label="快捷键说明">
      <div class="hint-item"><kbd>Enter</kbd><span>通过</span></div>
      <div class="hint-item"><kbd>R</kbd><span>驳回</span></div>
      <div class="hint-item"><kbd>Esc</kbd><span>取消</span></div>
      <div class="hint-item"><kbd>Ctrl+A</kbd><span>全选</span></div>
    </div>
  </div>
</template>

<style scoped>
.approval-view { display: flex; flex-direction: column; gap: var(--space-xl); }

/* ── Page Header ────────────────────────────────────────────── */
.page-header { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-size: var(--text-3xl); font-weight: 600; color: var(--text-primary); margin: 0 0 var(--space-xs) 0; }
.page-subtitle { font-size: var(--text-md); color: var(--text-tertiary); margin: 0; }
.page-actions { display: flex; align-items: center; gap: var(--space-md); }
.page-actions .btn.active { background: var(--primary-light); color: var(--primary); border-color: var(--primary); }

.stat-badge { padding: var(--space-sm) var(--space-lg); background: var(--bg-hover); color: var(--text-secondary); font-size: var(--text-md); font-weight: 500; border-radius: var(--radius-full); }
.stat-badge.has-items { background: var(--primary-light); color: var(--primary); }

/* ── Batch Bar ───────────────────────────────────────────────── */
.batch-bar { display: flex; justify-content: space-between; align-items: center; padding: var(--space-md) var(--space-lg); background: var(--primary-light); border-radius: var(--radius-lg); border: 1px solid var(--primary); }
.batch-left { display: flex; align-items: center; gap: var(--space-lg); }
.batch-checkbox { display: flex; align-items: center; gap: var(--space-sm); cursor: pointer; font-size: var(--text-sm); color: var(--text-primary); }
.batch-checkbox input[type="checkbox"] { width: 20px; height: 20px; cursor: pointer; }
.batch-count { font-size: var(--text-sm); color: var(--primary); font-weight: 500; }
.batch-right { display: flex; gap: var(--space-sm); }

/* ── Loading Spinner ─────────────────────────────────────────── */
.loading-spinner-sm { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255, 255, 255, 0.3); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: var(--space-xs); }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Slide Transition ────────────────────────────────────────── */
.slide-enter-active, .slide-leave-active { transition: all 0.3s ease; }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateY(-10px); }

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .page-header { flex-direction: column; gap: var(--space-md); }
  .page-actions { width: 100%; justify-content: flex-end; }
}
</style>
