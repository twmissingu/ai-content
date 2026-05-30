<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import SkeletonLoader from '../components/SkeletonLoader.vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

interface SourceItem {
  title: string
  description?: string
  url?: string
  source: string
  hot_value?: number
  final_score?: number
  raw_score?: number
  freshness?: number
  tier?: string
}

interface Stats {
  total_items: number
  by_source: Record<string, number>
  avg_score: number
  file_count: number
}

const items = ref<SourceItem[]>([])
const stats = ref<Stats | null>(null)
const loading = ref(false)
const statsLoading = ref(false)
const error = ref<string | null>(null)

// Filters
const filterSource = ref('')
const filterMinScore = ref(0)
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)

const sources = computed(() => {
  if (!stats.value) return []
  return Object.keys(stats.value.by_source).sort()
})

async function fetchItems() {
  loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams()
    if (filterSource.value) params.set('source', filterSource.value)
    if (filterMinScore.value > 0) params.set('min_score', String(filterMinScore.value))
    params.set('limit', String(pageSize))
    params.set('offset', String((currentPage.value - 1) * pageSize))

    const res = await fetch(`${API_BASE}/api/sources?${params}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  statsLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/sources/stats`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    stats.value = await res.json()
  } catch (e) {
    console.error('Failed to load stats:', e)
  } finally {
    statsLoading.value = false
  }
}

function applyFilters() {
  currentPage.value = 1
  fetchItems()
}

function clearFilters() {
  filterSource.value = ''
  filterMinScore.value = 0
  currentPage.value = 1
  fetchItems()
}

function getSourceIcon(source: string): string {
  const icons: Record<string, string> = {
    twitter: '🐦', github: '🐙', zhihu: '💡', weibo: '🔥',
    bilibili: '📺', baidu: '🔍', rss: '📰', web_search: '🌐',
    materials: '📚', douyin: '🎵', toutiao: '📰', kr36: '🔬',
    firecrawl: '🕷️',
  }
  return icons[source] || '📌'
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'success'
  if (score >= 60) return 'primary'
  if (score >= 40) return 'warning'
  return 'neutral'
}

function getTierLabel(tier: string): string {
  const labels: Record<string, string> = { T1: 'T1', 'T1.5': 'T1.5', T2: 'T2' }
  return labels[tier] || tier || '-'
}

function truncate(text: string, max: number = 80): string {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

const totalPages = computed(() => Math.ceil(total.value / pageSize))

onMounted(() => {
  fetchItems()
  fetchStats()
})
</script>

<template>
  <div class="sources-view">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title">信源流</h2>
        <p class="page-subtitle">Scout 采集的原始信源数据</p>
      </div>
      <button class="btn btn-ghost btn-sm" @click="fetchItems(); fetchStats()">刷新</button>
    </div>

    <!-- Stats Cards -->
    <div v-if="stats" class="stats-grid">
      <div class="card stat-card">
        <span class="stat-value">{{ stats.total_items }}</span>
        <span class="stat-label">总条目</span>
      </div>
      <div class="card stat-card">
        <span class="stat-value">{{ Object.keys(stats.by_source).length }}</span>
        <span class="stat-label">信源数</span>
      </div>
      <div class="card stat-card">
        <span class="stat-value">{{ stats.avg_score }}</span>
        <span class="stat-label">平均分</span>
      </div>
      <div class="card stat-card">
        <span class="stat-value">{{ stats.file_count }}</span>
        <span class="stat-label">采集批次</span>
      </div>
    </div>

    <!-- Filters -->
    <div class="card filter-bar">
      <div class="filter-group">
        <label class="filter-label">信源</label>
        <select v-model="filterSource" class="filter-select" @change="applyFilters">
          <option value="">全部</option>
          <option v-for="s in sources" :key="s" :value="s">{{ s }} ({{ stats?.by_source[s] }})</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">最低分</label>
        <input
          v-model.number="filterMinScore"
          type="number"
          min="0"
          max="100"
          class="filter-input"
          placeholder="0"
          @change="applyFilters"
        >
      </div>
      <button class="btn btn-ghost btn-sm" @click="clearFilters">清除</button>
    </div>

    <!-- Error -->
    <div v-if="error" class="card error-banner" role="alert">
      <span>⚠️ {{ error }}</span>
      <button class="btn btn-ghost btn-sm" @click="fetchItems">重试</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="table-skeleton">
      <SkeletonLoader type="text" :count="8" />
    </div>

    <!-- Table -->
    <div v-else-if="items.length > 0" class="card table-wrapper">
      <table class="sources-table">
        <thead>
          <tr>
            <th>标题</th>
            <th>信源</th>
            <th>热度</th>
            <th>新鲜度</th>
            <th>层级</th>
            <th>评分</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, i) in items" :key="i">
            <td class="col-title">
              <a v-if="item.url" :href="item.url" target="_blank" rel="noopener" class="item-link">
                {{ truncate(item.title, 60) }}
              </a>
              <span v-else>{{ truncate(item.title, 60) }}</span>
            </td>
            <td>
              <span class="source-badge">
                <span class="source-icon">{{ getSourceIcon(item.source) }}</span>
                {{ item.source }}
              </span>
            </td>
            <td class="col-number">{{ item.hot_value ?? '-' }}</td>
            <td class="col-number">{{ item.freshness ?? '-' }}</td>
            <td><span class="tier-badge">{{ getTierLabel(item.tier || '') }}</span></td>
            <td>
              <span
                v-if="item.final_score || item.raw_score"
                class="score-pill"
                :class="getScoreColor(item.final_score || item.raw_score || 0)"
              >
                {{ Math.round(item.final_score || item.raw_score || 0) }}
              </span>
              <span v-else>-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Empty -->
    <div v-else class="card empty-state">
      <div class="empty-icon">📡</div>
      <div class="empty-title">暂无信源数据</div>
      <div class="empty-desc">等待 Scout 采集运行后，信源数据将在此显示</div>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="pagination-bar">
      <button class="btn btn-ghost btn-sm" :disabled="currentPage <= 1" @click="currentPage--; fetchItems()">上一页</button>
      <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
      <button class="btn btn-ghost btn-sm" :disabled="currentPage >= totalPages" @click="currentPage++; fetchItems()">下一页</button>
    </div>
  </div>
</template>

<style scoped>
.sources-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

/* ── Header ─────────────────────────────────────────────────── */
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

/* ── Stats ──────────────────────────────────────────────────── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-md);
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-lg);
}

.stat-value {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-top: var(--space-xs);
}

/* ── Filters ────────────────────────────────────────────────── */
.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--space-lg);
  padding: var(--space-md) var(--space-lg);
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.filter-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: 500;
}

.filter-select,
.filter-input {
  padding: var(--space-xs) var(--space-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-family: var(--font-family);
}

.filter-input {
  width: 80px;
}

/* ── Table ──────────────────────────────────────────────────── */
.table-wrapper {
  overflow-x: auto;
  padding: 0;
}

.sources-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.sources-table th {
  text-align: left;
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
}

.sources-table td {
  padding: var(--space-sm) var(--space-md);
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
  vertical-align: middle;
}

.sources-table tr:hover td {
  background: var(--bg-hover);
}

.col-title {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-number {
  font-family: var(--font-mono);
  text-align: right;
}

.item-link {
  color: var(--primary);
  text-decoration: none;
}

.item-link:hover {
  text-decoration: underline;
}

.source-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  padding: 2px 8px;
  background: var(--bg-hover);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.source-icon {
  font-size: var(--text-md);
}

.tier-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 600;
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.score-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: 600;
}

.score-pill.success {
  background: var(--success-light, #d1fae5);
  color: var(--success-dark, #065f46);
}

.score-pill.primary {
  background: var(--primary-light);
  color: var(--primary);
}

.score-pill.warning {
  background: var(--warning-light, #fef3c7);
  color: var(--warning-dark, #92400e);
}

.score-pill.neutral {
  background: var(--bg-hover);
  color: var(--text-tertiary);
}

/* ── States ─────────────────────────────────────────────────── */
.table-skeleton {
  padding: var(--space-lg);
}

.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  padding: var(--space-md) var(--space-lg);
  background: var(--danger-light);
  color: var(--danger);
  border-left: 3px solid var(--danger);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-4xl);
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: var(--space-md);
  opacity: 0.5;
}

.empty-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-sm);
}

.empty-desc {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

/* ── Pagination ─────────────────────────────────────────────── */
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
}

.page-info {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

/* ── Responsive ─────────────────────────────────────────────── */
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .filter-bar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
