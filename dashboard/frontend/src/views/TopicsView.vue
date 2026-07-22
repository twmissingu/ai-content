<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import SkeletonLoader from '../components/SkeletonLoader.vue'
import PaginationBar from '../components/PaginationBar.vue'
import ReaderPanel from '../components/ReaderPanel.vue'
import { useKeyboardShortcut, isInputElement } from '../composables/useKeyboardShortcut'

const store = useDashboardStore()

// Reader panel state
const readerUrl = ref<string | null>(null)
const readerVisible = ref(false)

function openReader(url: string) {
  readerUrl.value = url
  readerVisible.value = true
}

function closeReader() {
  readerVisible.value = false
}

// Pagination
const currentPage = ref(1)
const pageSize = 10
const paginatedTopics = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return store.topics.slice(start, start + pageSize)
})

const topicCount = computed(() => store.topics.length)

function getScoreColor(score: number): string {
  if (score >= 85) return 'success'
  if (score >= 70) return 'primary'
  if (score >= 55) return 'warning'
  return 'neutral'
}

function getScoreLabel(score: number): string {
  if (score >= 85) return '强推'
  if (score >= 70) return '候选'
  if (score >= 55) return '待定'
  return '较低'
}

function getSourceIcon(source: string): string {
  const icons: Record<string, string> = {
    twitter: '🐦',
    github: '🐙',
    zhihu: '💡',
    weibo: '🔥',
    bilibili: '📺',
    baidu: '🔍',
    rss: '📰',
    web_search: '🌐',
    materials: '📚',
  }
  return icons[source] || '📌'
}

function truncateText(text: string, maxLen: number = 150): string {
  if (!text) return ''
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

// ── Keyboard shortcuts ──────────────────────────────────────────────
function handleKeydown(e: KeyboardEvent) {
  if (isInputElement(e.target)) return
  const totalPages = Math.ceil(topicCount.value / pageSize)
  if (e.key === 'ArrowLeft' && currentPage.value > 1) {
    currentPage.value--
  } else if (e.key === 'ArrowRight' && currentPage.value < totalPages) {
    currentPage.value++
  }
}

useKeyboardShortcut(handleKeydown)
</script>

<template>
  <div class="topics-view-wrapper">
    <div class="topics-view">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title">今日选题</h2>
        <p class="page-subtitle">Scout 推荐的热门选题候选</p>
      </div>
      <div class="page-stats">
        <span class="stat-badge" :class="{ 'has-items': topicCount > 0 }">
          {{ topicCount }} 个候选
        </span>
      </div>
    </div>

    <!-- Loading Skeletons -->
    <div v-if="store.isLoading('topics') && store.topics.length === 0" class="topics-grid">
      <div v-for="i in 3" :key="i" class="card topic-card-skeleton">
        <SkeletonLoader type="title" width="80%" />
        <SkeletonLoader type="text" :count="2" />
        <SkeletonLoader type="card" height="80px" />
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="store.error && store.topics.length === 0" class="card error-state">
      <div class="error-icon">⚠️</div>
      <div class="error-title">加载选题失败</div>
      <p class="error-message">{{ store.error }}</p>
      <button class="btn btn-primary" @click="store.fetchTopics()">
        🔄 重试
      </button>
    </div>

    <!-- Empty State -->
    <div v-else-if="store.topics.length === 0" class="card empty-state">
      <div class="empty-state-icon">🔍</div>
      <div class="empty-state-title">暂无候选选题</div>
      <div class="empty-state-description">
        等待 Scout Agent 执行选题任务，通常在 09:00 和 14:00 触发
      </div>
      <router-link to="/pipeline" class="btn btn-primary">
        📊 查看管线状态
      </router-link>
    </div>

    <!-- Topics Grid -->
    <div v-else class="topics-grid">
      <div v-for="topic in paginatedTopics" :key="topic.id" class="card topic-card">
        <!-- Topic Header -->
        <div class="topic-header">
          <h3 class="topic-title">{{ topic.title }}</h3>
        </div>

        <!-- Topic Meta -->
        <div class="topic-meta">
          <span class="meta-item">
            <span class="meta-icon">{{ getSourceIcon(topic.source) }}</span>
            {{ topic.source }}
          </span>
          <span v-if="topic.direction" class="meta-item">
            <span class="meta-icon">📁</span>
            {{ topic.direction }}
          </span>
        </div>

        <!-- Description -->
        <div v-if="topic.description" class="topic-description">
          {{ truncateText(topic.description) }}
        </div>

        <!-- Score Summary -->
        <div class="topic-score-summary" :class="getScoreColor(topic.final_score || 0)">
          <div class="score-main">
            <span class="score-value">{{ topic.final_score || 0 }}</span>
            <span class="score-label">{{ getScoreLabel(topic.final_score || 0) }}</span>
          </div>
          <div class="score-details">
            <span class="score-detail">热度 {{ topic.viral_score || 0 }}</span>
            <span class="score-detail">新颖 {{ topic.novelty_score || 0 }}</span>
            <span class="score-detail">可行 {{ topic.feasibility_score || 0 }}</span>
            <span class="score-detail">饱和 {{ topic.saturation_score || 0 }}</span>
          </div>
        </div>

        <!-- Score Breakdown -->
        <div class="score-breakdown">
          <div class="score-row">
            <span class="score-label">热度</span>
            <div class="score-bar-track">
              <div class="score-bar-fill" :style="{ width: (topic.viral_score || 0) + '%' }"></div>
            </div>
            <span class="score-value">{{ topic.viral_score || 0 }}</span>
          </div>
          <div class="score-row">
            <span class="score-label">新颖</span>
            <div class="score-bar-track">
              <div class="score-bar-fill" :style="{ width: (topic.novelty_score || 0) + '%' }"></div>
            </div>
            <span class="score-value">{{ topic.novelty_score || 0 }}</span>
          </div>
          <div class="score-row">
            <span class="score-label">可行</span>
            <div class="score-bar-track">
              <div class="score-bar-fill" :style="{ width: (topic.feasibility_score || 0) + '%' }"></div>
            </div>
            <span class="score-value">{{ topic.feasibility_score || 0 }}</span>
          </div>
          <div class="score-row">
            <span class="score-label">饱和</span>
            <div class="score-bar-track">
              <div class="score-bar-fill" :style="{ width: (topic.saturation_score || 0) + '%' }"></div>
            </div>
            <span class="score-value">{{ topic.saturation_score || 0 }}</span>
          </div>
        </div>

        <!-- Source Link -->
        <div v-if="topic.url" class="topic-link">
          <a :href="topic.url" target="_blank" rel="noopener noreferrer">
            <span>🔗</span> 查看原文
          </a>
          <button class="btn btn-ghost btn-xs" @click="openReader(topic.url)" title="在面板中阅读" aria-label="在面板中阅读原文">
            📖
          </button>
        </div>

        <!-- Confirm Button -->
        <button
          class="btn btn-primary btn-block"
          @click="store.confirmTopic(topic.id)"
          :disabled="store.isLoading('confirmTopic')"
        >
          ✅ 确认选题
        </button>
      </div>
    </div>

    <!-- Pagination -->
    <PaginationBar
      v-if="store.topics.length > pageSize"
      :total="store.topics.length"
      :page-size="pageSize"
      :current-page="currentPage"
      @update:currentPage="currentPage = $event"
    />

    <!-- Keyboard Shortcuts Hint -->
    <div v-if="store.topics.length > 0" class="keyboard-hints" role="region" aria-label="快捷键说明">
      <div class="hint-item"><kbd>&larr;</kbd><span>上一页</span></div>
      <div class="hint-item"><kbd>&rarr;</kbd><span>下一页</span></div>
    </div>
  </div>

  <!-- Reader Panel -->
  <ReaderPanel
    :url="readerUrl"
    :visible="readerVisible"
    @close="closeReader"
  />
  </div>
</template>

<style scoped>
.topics-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-2xl);
}

/* ── Page Header ─────────────────────────────────────────────── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-lg);
  padding: var(--space-xl);
  background: rgba(255, 253, 248, 0.58);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-2xl);
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: 650;
  color: var(--text-primary);
  letter-spacing: -0.025em;
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
  background: rgba(255, 253, 248, 0.76);
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 650;
  border-radius: var(--radius-full);
}

.stat-badge.has-items {
  background: var(--success-light);
  border-color: rgba(95, 127, 101, 0.22);
  color: var(--success);
}

/* ── Topics Grid ─────────────────────────────────────────────── */
.topics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-lg);
}

/* ── Topic Card ──────────────────────────────────────────────── */
.topic-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  background: var(--surface-glow);
  transition: border-color var(--transition-normal), box-shadow var(--transition-normal), transform var(--transition-normal);
}

.topic-card:hover {
  border-color: var(--border-color);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

/* ── Topic Content ───────────────────────────────────────────── */
.topic-header {
  padding-right: 0;
}

.topic-title {
  font-size: var(--text-lg);
  font-weight: 650;
  color: var(--text-primary);
  letter-spacing: -0.01em;
  margin: 0;
  line-height: 1.55;
}

.topic-meta {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  min-height: 24px;
  padding: 1px 7px;
  background: rgba(248, 244, 236, 0.72);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.meta-icon {
  font-size: var(--text-sm);
  opacity: 0.72;
  filter: grayscale(0.22);
}

.topic-description {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.75;
}

/* ── Score Summary ───────────────────────────────────────────── */
.topic-score-summary {
  display: flex;
  align-items: center;
  gap: var(--space-lg);
  padding: var(--space-md);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  background: rgba(248, 244, 236, 0.68);
}

.topic-score-summary.success {
  background: var(--success-light);
  border-color: rgba(95, 127, 101, 0.18);
}

.topic-score-summary.primary {
  background: var(--primary-light);
  border-color: rgba(77, 100, 117, 0.18);
}

.topic-score-summary.warning {
  background: var(--warning-light);
  border-color: rgba(185, 137, 72, 0.18);
}

.topic-score-summary.neutral {
  background: rgba(248, 244, 236, 0.68);
}

.score-main {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 48px;
}

.score-main .score-value {
  font-size: var(--text-2xl);
  font-weight: 750;
  line-height: 1;
  letter-spacing: -0.02em;
}

.score-main .score-label {
  font-size: var(--text-xs);
  font-weight: 600;
  margin-top: 3px;
}

.topic-score-summary.success .score-main { color: var(--success); }
.topic-score-summary.primary .score-main { color: var(--primary-dark); }
.topic-score-summary.warning .score-main { color: var(--warning); }
.topic-score-summary.neutral .score-main { color: var(--text-secondary); }

.score-details {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
}

.score-detail {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  padding: 2px 7px;
  background: rgba(255, 253, 248, 0.72);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
}

/* ── Score Breakdown ─────────────────────────────────────────── */
.score-breakdown {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  padding: var(--space-md);
  background: rgba(248, 244, 236, 0.58);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
}

.score-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.score-row .score-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  min-width: 32px;
}

.score-row .score-bar-track {
  flex: 1;
  height: 5px;
  background: var(--border-light);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.score-row .score-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--primary-light));
  border-radius: var(--radius-full);
  transition: width var(--transition-slow);
}

.score-row .score-value {
  font-size: var(--text-xs);
  font-weight: 650;
  color: var(--text-secondary);
  min-width: 28px;
  text-align: right;
}

/* ── Source Link ─────────────────────────────────────────────── */
.topic-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  font-size: var(--text-sm);
}

.topic-link a {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  color: var(--primary-dark);
  text-decoration: none;
  transition: color var(--transition-fast);
}

.topic-link a:hover {
  color: var(--primary-hover);
  text-decoration: underline;
  text-underline-offset: 3px;
}

/* ── Empty / Error State ─────────────────────────────────────── */
.empty-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-4xl);
  text-align: center;
  background-image: var(--paper-grain);
  background-size: 8px 8px;
}

.empty-state-icon,
.error-icon {
  font-size: 48px;
  margin-bottom: var(--space-lg);
  opacity: 0.64;
  filter: grayscale(0.18);
}

.empty-state-title,
.error-title {
  font-size: var(--text-2xl);
  font-weight: 650;
  color: var(--text-primary);
  margin-bottom: var(--space-sm);
}

.empty-state-description,
.error-message {
  font-size: var(--text-md);
  color: var(--text-tertiary);
  max-width: 420px;
  margin-bottom: var(--space-xl);
  line-height: 1.7;
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .topics-grid { grid-template-columns: 1fr; }
}
</style>
