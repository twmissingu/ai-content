<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'

const store = useDashboardStore()
const selectedId = ref<string | null>(null)
const rejectReason = ref('')
const showRejectInput = ref<string | null>(null)

function select(id: string) {
  selectedId.value = selectedId.value === id ? null : id
}

function doReject(id: string) {
  if (!rejectReason.value.trim()) return
  store.reject(id, rejectReason.value)
  showRejectInput.value = null
  rejectReason.value = ''
}

function cancelReject() {
  showRejectInput.value = null
  rejectReason.value = ''
}

const pendingCount = computed(() => store.approvalQueue.length)
</script>

<template>
  <div class="approval-view">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title">审批队列</h2>
        <p class="page-subtitle">审核并发布内容到各平台</p>
      </div>
      <div class="page-stats">
        <span class="stat-badge" :class="{ 'has-items': pendingCount > 0 }">
          {{ pendingCount }} 篇待审
        </span>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="store.approvalQueue.length === 0" class="card empty-state">
      <div class="empty-state-icon">✅</div>
      <div class="empty-state-title">暂无待审批文章</div>
      <div class="empty-state-description">
        所有文章已审批完毕，等待下一轮 Writer 生产
      </div>
    </div>

    <!-- Article List -->
    <div v-for="article in store.approvalQueue" :key="article.id" class="card article-card">
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
          <button 
            class="btn btn-success btn-sm" 
            @click.stop="store.approve(article.id)"
          >
            ✅ 通过
          </button>
          <button 
            v-if="showRejectInput !== article.id" 
            class="btn btn-danger btn-sm"
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
              @keyup.enter="doReject(article.id)"
            >
            <button 
              class="btn btn-danger" 
              :disabled="!rejectReason.trim()" 
              @click="doReject(article.id)"
            >
              确认驳回
            </button>
            <button class="btn btn-ghost" @click="cancelReject">
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
            <div class="preview-text">{{ article.content_preview }}</div>
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
}

.article-card:hover {
  box-shadow: var(--shadow-lg);
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
  white-space: pre-wrap;
  word-break: break-word;
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
