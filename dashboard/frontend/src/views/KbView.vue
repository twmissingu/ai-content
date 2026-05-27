<script setup lang="ts">
import { ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
const query = ref('')
const results = ref<any[]>([])
const sections = ref<any[]>([])
const searched = ref(false)
const loading = ref(false)
const loadingSections = ref(false)
const selectedSection = ref<string | null>(null)

async function search() {
  if (!query.value.trim()) return
  searched.value = true
  loading.value = true
  
  try {
    const sectionParam = selectedSection.value ? `&section=${selectedSection.value}` : ''
    const res = await fetch(`${API_BASE}/api/kb/search?q=${encodeURIComponent(query.value)}${sectionParam}`)
    const data = await res.json()
    results.value = data.results || []
  } catch (e) {
    console.error('Search failed:', e)
    results.value = []
  } finally {
    loading.value = false
  }
}

async function fetchSections() {
  loadingSections.value = true
  try {
    const res = await fetch(`${API_BASE}/api/kb/sections`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    sections.value = data.sections || []
  } catch (e) {
    console.error('Failed to fetch sections:', e)
    sections.value = []
  } finally {
    loadingSections.value = false
  }
}

function selectSection(name: string) {
  selectedSection.value = selectedSection.value === name ? null : name
  if (searched.value) {
    search()
  }
}

function getSectionIcon(name: string): string {
  const icons: Record<string, string> = {
    topics: '💡',
    viral: '🔥',
    history: '📚',
    strategy: '🎯',
    materials: '📦',
  }
  return icons[name] || '📁'
}

function clearSearch() {
  query.value = ''
  results.value = []
  searched.value = false
  selectedSection.value = null
}

function highlightMatch(text: string, keyword: string): string {
  if (!keyword || !text) return text
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
  const regex = new RegExp(`(${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return escaped.replace(regex, '<mark class="highlight">$1</mark>')
}

fetchSections()
</script>

<template>
  <div class="kb-view">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title">知识库</h2>
        <p class="page-subtitle">搜索和浏览沉淀的内容资产</p>
      </div>
    </div>

    <!-- Search Bar -->
    <div class="card search-card">
      <div class="search-input-group">
        <span class="search-icon">🔍</span>
        <input
          v-model="query"
          @keyup.enter="search"
          class="search-input"
          placeholder="搜索知识库文章..."
        >
        <button 
          v-if="query" 
          class="btn btn-ghost btn-sm clear-btn"
          @click="clearSearch"
        >
          ✕
        </button>
        <button 
          class="btn btn-primary" 
          @click="search"
          :disabled="!query.trim() || loading"
        >
          <span v-if="loading" class="loading-spinner"></span>
          <span v-else>搜索</span>
        </button>
      </div>
    </div>

    <!-- Sections Overview -->
    <div class="sections-grid">
      <div v-if="loadingSections" class="card section-card loading">
        <div class="loading-spinner"></div>
        <span>加载分类...</span>
      </div>
      <template v-else>
        <div 
          v-for="s in sections" 
          :key="s.name"
          class="card section-card"
          :class="{ active: selectedSection === s.name }"
          @click="selectSection(s.name)"
        >
          <span class="section-icon">{{ getSectionIcon(s.name) }}</span>
          <div class="section-info">
            <span class="section-name">{{ s.name }}</span>
            <span class="section-count">{{ s.count }} 篇</span>
          </div>
        </div>
      </template>
    </div>

    <!-- Search Results -->
    <div v-if="searched" class="results-section">
      <!-- Loading -->
      <div v-if="loading" class="card loading-state">
        <div class="loading-spinner large"></div>
        <span>搜索中...</span>
      </div>

      <!-- Results -->
      <template v-else>
        <div class="results-header">
          <span class="results-count">找到 {{ results.length }} 条结果</span>
          <span v-if="selectedSection" class="results-filter">
            筛选: {{ selectedSection }}
            <button class="btn btn-ghost btn-xs" @click="selectedSection = null; search()">✕</button>
          </span>
        </div>

        <!-- Empty Results -->
        <div v-if="results.length === 0" class="card empty-state">
          <div class="empty-state-icon">🔍</div>
          <div class="empty-state-title">未找到匹配结果</div>
          <div class="empty-state-description">
            尝试使用不同的关键词或清除筛选条件
          </div>
        </div>

        <!-- Result List -->
        <div v-for="r in results" :key="r.path" class="card result-card">
          <div class="result-header">
            <span class="result-icon">{{ getSectionIcon(r.section || r.type) }}</span>
            <div class="result-info">
              <h4 class="result-title">{{ r.title }}</h4>
              <div class="result-meta">
                <span class="meta-item">{{ r.section || r.type }}</span>
                <span class="meta-divider">·</span>
                <span class="meta-item path">{{ r.path }}</span>
              </div>
            </div>
          </div>
          <div v-if="r.match" class="result-match">
            <span class="match-text" v-html="'...' + highlightMatch(r.match, query) + '...'"></span>
          </div>
        </div>
      </template>
    </div>

    <!-- Initial State -->
    <div v-if="!searched" class="card initial-state">
      <div class="initial-icon">📚</div>
      <div class="initial-title">知识库检索</div>
      <div class="initial-description">
        输入关键词搜索历史文章、爆款分析、写作策略等内容
      </div>
      <div class="initial-tips">
        <div class="tip-title">搜索技巧：</div>
        <ul class="tip-list">
          <li>使用中文关键词进行搜索</li>
          <li>选择特定分类缩小范围</li>
          <li>点击分类标签进行快速筛选</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kb-view {
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

/* ── Search Card ─────────────────────────────────────────────── */
.search-card {
  padding: var(--space-lg);
}

.search-input-group {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  background: var(--bg-hover);
  border-radius: var(--radius-lg);
  padding: var(--space-sm) var(--space-md);
  transition: all var(--transition-fast);
}

.search-input-group:focus-within {
  background: var(--bg-card);
  box-shadow: 0 0 0 2px var(--primary-light);
}

.search-icon {
  font-size: var(--text-xl);
  color: var(--text-tertiary);
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: var(--text-md);
  font-family: var(--font-family);
  color: var(--text-primary);
  outline: none;
  padding: var(--space-sm) 0;
}

.search-input::placeholder {
  color: var(--text-disabled);
}

.clear-btn {
  color: var(--text-tertiary);
  padding: var(--space-xs) var(--space-sm);
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-spinner.large {
  width: 24px;
  height: 24px;
  border-width: 3px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Sections Grid ───────────────────────────────────────────── */
.sections-grid {
  display: flex;
  gap: var(--space-md);
  flex-wrap: wrap;
}

.section-card {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md) var(--space-lg);
  cursor: pointer;
  transition: all var(--transition-fast);
  min-width: 120px;
}

.section-card.loading {
  cursor: default;
  opacity: 0.7;
}

.section-card:hover {
  background: var(--bg-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.section-card.active {
  background: var(--primary-light);
  border: 1px solid var(--primary);
}

.section-icon {
  font-size: var(--text-2xl);
}

.section-info {
  display: flex;
  flex-direction: column;
}

.section-name {
  font-size: var(--text-md);
  font-weight: 500;
  color: var(--text-primary);
  text-transform: capitalize;
}

.section-count {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

/* ── Results Section ─────────────────────────────────────────── */
.results-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-xs);
}

.results-count {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

.results-filter {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--text-sm);
  color: var(--primary);
  background: var(--primary-light);
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-full);
}

.btn-xs {
  padding: 2px 6px;
  font-size: var(--text-xs);
}

/* ── Result Card ─────────────────────────────────────────────── */
.result-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  transition: all var(--transition-fast);
}

.result-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}

.result-header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
}

.result-icon {
  font-size: var(--text-2xl);
  line-height: 1;
}

.result-info {
  flex: 1;
  min-width: 0;
}

.result-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-xs) 0;
}

.result-meta {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.meta-item {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.meta-item.path {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.meta-divider {
  color: var(--text-disabled);
}

.result-match {
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  border-left: 3px solid var(--primary);
}

.match-text {
  font-size: var(--text-md);
  color: var(--text-secondary);
  line-height: 1.6;
}

.match-text :deep(.highlight) {
  background: var(--warning-light);
  color: var(--warning-dark);
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 500;
}

/* ── Loading State ───────────────────────────────────────────── */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  padding: var(--space-4xl);
  color: var(--text-tertiary);
}

/* ── Empty State ─────────────────────────────────────────────── */
.empty-state {
  padding: var(--space-4xl);
}

/* ── Initial State ───────────────────────────────────────────── */
.initial-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-4xl);
  text-align: center;
}

.initial-icon {
  font-size: 64px;
  margin-bottom: var(--space-lg);
  opacity: 0.6;
}

.initial-title {
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-sm);
}

.initial-description {
  font-size: var(--text-md);
  color: var(--text-tertiary);
  max-width: 400px;
  margin-bottom: var(--space-2xl);
}

.initial-tips {
  background: var(--bg-hover);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  text-align: left;
  max-width: 360px;
}

.tip-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-md);
}

.tip-list {
  margin: 0;
  padding-left: var(--space-lg);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.8;
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .sections-grid {
    overflow-x: auto;
    flex-wrap: nowrap;
    padding-bottom: var(--space-sm);
  }
  
  .section-card {
    min-width: 100px;
  }
}
</style>
