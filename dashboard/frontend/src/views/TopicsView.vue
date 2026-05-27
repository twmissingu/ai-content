<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'

const store = useDashboardStore()

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
</script>

<template>
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

    <!-- Empty State -->
    <div v-if="store.topics.length === 0" class="card empty-state">
      <div class="empty-state-icon">🔍</div>
      <div class="empty-state-title">暂无候选选题</div>
      <div class="empty-state-description">
        等待 Scout Agent 执行选题任务，通常在 09:00 和 14:00 触发
      </div>
    </div>

    <!-- Topics Grid -->
    <div class="topics-grid">
      <div v-for="topic in store.topics" :key="topic.id" class="card topic-card">
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
        </div>

        <!-- Confirm Button -->
        <button 
          class="btn btn-primary btn-block" 
          @click="store.confirmTopic(topic.id)"
        >
          ✅ 确认选题
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.topics-view {
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
  background: var(--success-light);
  color: var(--success);
}

/* ── Topics Grid ─────────────────────────────────────────────── */
.topics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-lg);
}

/* ── Topic Card ──────────────────────────────────────────────── */
.topic-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  position: relative;
  transition: all var(--transition-normal);
}

.topic-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}

/* ── Topic Content ───────────────────────────────────────────── */
.topic-header {
  padding-right: 0;
}

.topic-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.4;
}

.topic-meta {
  display: flex;
  align-items: center;
  gap: var(--space-md);
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

.topic-description {
  font-size: var(--text-md);
  color: var(--text-secondary);
  line-height: 1.6;
}

/* ── Score Summary ───────────────────────────────────────────── */
.topic-score-summary {
  display: flex;
  align-items: center;
  gap: var(--space-lg);
  padding: var(--space-md);
  border-radius: var(--radius-lg);
  background: var(--bg-hover);
}

.topic-score-summary.success {
  background: var(--success-light);
}

.topic-score-summary.primary {
  background: var(--primary-light);
}

.topic-score-summary.warning {
  background: var(--warning-light);
}

.topic-score-summary.neutral {
  background: var(--bg-hover);
}

.score-main {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 48px;
}

.score-main .score-value {
  font-size: var(--text-2xl);
  font-weight: 700;
  line-height: 1;
}

.score-main .score-label {
  font-size: var(--text-xs);
  font-weight: 500;
  margin-top: 2px;
}

.topic-score-summary.success .score-main {
  color: var(--success);
}

.topic-score-summary.primary .score-main {
  color: var(--primary);
}

.topic-score-summary.warning .score-main {
  color: var(--warning-dark);
}

.topic-score-summary.neutral .score-main {
  color: var(--text-secondary);
}

.score-details {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
}

.score-detail {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  padding: 2px 6px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
}

/* ── Score Breakdown ─────────────────────────────────────────── */
.score-breakdown {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  padding: var(--space-md);
  background: var(--bg-hover);
  border-radius: var(--radius-lg);
}

.score-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.score-row .score-label {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  min-width: 32px;
}

.score-row .score-bar-track {
  flex: 1;
  height: 4px;
  background: var(--border-color);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.score-row .score-bar-fill {
  height: 100%;
  background: var(--primary);
  border-radius: var(--radius-full);
  transition: width var(--transition-slow);
}

.score-row .score-value {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 28px;
  text-align: right;
}

/* ── Source Link ─────────────────────────────────────────────── */
.topic-link {
  font-size: var(--text-sm);
}

.topic-link a {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  color: var(--primary);
  text-decoration: none;
  transition: color var(--transition-fast);
}

.topic-link a:hover {
  color: var(--primary-hover);
  text-decoration: underline;
}

/* ── Empty State ─────────────────────────────────────────────── */
.empty-state {
  padding: var(--space-4xl);
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .topics-grid {
    grid-template-columns: 1fr;
  }
}
</style>
