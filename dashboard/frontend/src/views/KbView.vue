<script setup lang="ts">
import { ref, onMounted } from 'vue'
import SkeletonLoader from '../components/SkeletonLoader.vue'
import { useKeyboardShortcut, isInputElement } from '../composables/useKeyboardShortcut'
import { API_BASE } from '../utils/api'



// ── Directory tree state ──
interface TreeNode {
  name: string
  path: string
  type: 'directory' | 'file'
  children?: TreeNode[]
  size?: number
  expanded?: boolean
}

const tree = ref<TreeNode[]>([])
const treeLoading = ref(false)
const selectedFilePath = ref<string | null>(null)
const fileContent = ref<string | null>(null)
const fileLoading = ref(false)
const fileError = ref<string | null>(null)

// ── Search state ──
const searchInputRef = ref<HTMLInputElement | null>(null)
const query = ref('')
const results = ref<any[]>([])
const sections = ref<any[]>([])
const searched = ref(false)
const loading = ref(false)
const loadingSections = ref(false)
const selectedSection = ref<string | null>(null)
const searchError = ref<string | null>(null)
const sectionsError = ref<string | null>(null)

// ── Tree functions ──
async function fetchTree() {
  treeLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/kb/tree`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    tree.value = (data.tree || []).map(initNode)
  } catch (e) {
    console.error('Failed to load tree:', e)
  } finally {
    treeLoading.value = false
  }
}

function initNode(node: TreeNode): TreeNode {
  return { ...node, expanded: false, children: node.children?.map(initNode) }
}

function toggleNode(node: TreeNode) {
  if (node.type === 'directory') {
    node.expanded = !node.expanded
  } else {
    loadFile(node.path)
  }
}

async function loadFile(path: string) {
  selectedFilePath.value = path
  fileLoading.value = true
  fileError.value = null
  fileContent.value = null
  searched.value = false
  try {
    const res = await fetch(`${API_BASE}/api/kb/file?path=${encodeURIComponent(path)}`)
    if (!res.ok) throw new Error(`加载失败 (${res.status})`)
    const data = await res.json()
    fileContent.value = data.content
  } catch (e) {
    fileError.value = e instanceof Error ? e.message : '加载文件失败'
  } finally {
    fileLoading.value = false
  }
}

function closeFile() {
  selectedFilePath.value = null
  fileContent.value = null
  fileError.value = null
}

function getFileIcon(name: string): string {
  if (name.endsWith('.md')) return '📄'
  if (name.endsWith('.json')) return '📋'
  if (name.endsWith('.txt')) return '📝'
  return '📄'
}

// ── Search functions ──
async function search() {
  if (!query.value.trim()) return
  searched.value = true
  loading.value = true
  searchError.value = null
  closeFile()

  try {
    const sectionParam = selectedSection.value ? `&section=${selectedSection.value}` : ''
    const res = await fetch(`${API_BASE}/api/kb/search?q=${encodeURIComponent(query.value)}${sectionParam}`)
    if (!res.ok) throw new Error(`搜索失败 (${res.status})`)
    const data = await res.json()
    results.value = data.results || []
  } catch (e) {
    searchError.value = e instanceof Error ? e.message : '搜索失败，请重试'
    results.value = []
  } finally {
    loading.value = false
  }
}

async function fetchSections() {
  loadingSections.value = true
  sectionsError.value = null
  try {
    const res = await fetch(`${API_BASE}/api/kb/sections`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    sections.value = data.sections || []
  } catch (e) {
    sectionsError.value = e instanceof Error ? e.message : '加载分类失败'
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
  searchError.value = null
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

// ── Keyboard shortcuts ──────────────────────────────────────────────
function handleKeydown(e: KeyboardEvent) {
  if (isInputElement(e.target)) return
  if (e.key === '/') {
    e.preventDefault()
    searchInputRef.value?.focus()
  }
}

useKeyboardShortcut(handleKeydown)

onMounted(() => {
  fetchSections()
  fetchTree()
})
</script>

<template>
  <div class="kb-layout">
    <!-- Sidebar: Directory Tree -->
    <aside class="kb-sidebar">
      <div class="sidebar-header">
        <h3 class="sidebar-title">📁 目录</h3>
      </div>
      <div class="tree-container">
        <div v-if="treeLoading" class="tree-loading">
          <SkeletonLoader type="text" :count="6" />
        </div>
        <template v-else>
          <div v-if="tree.length === 0" class="tree-empty">暂无文件</div>
          <ul v-else class="tree-list" role="tree" aria-label="知识库目录">
            <li v-for="node in tree" :key="node.path">
              <div
                class="tree-node"
                :class="{ active: selectedFilePath === node.path, expanded: node.expanded }"
                role="treeitem"
                :aria-expanded="node.type === 'directory' ? node.expanded : undefined"
                :aria-selected="selectedFilePath === node.path"
                tabindex="0"
                @click="toggleNode(node)"
                @keydown.enter="toggleNode(node)"
                @keydown.space.prevent="toggleNode(node)"
              >
                <span v-if="node.type === 'directory'" class="tree-arrow">{{ node.expanded ? '▼' : '▶' }}</span>
                <span v-else class="tree-arrow-placeholder"></span>
                <span class="tree-icon">{{ node.type === 'directory' ? '📂' : getFileIcon(node.name) }}</span>
                <span class="tree-name">{{ node.name }}</span>
              </div>
              <ul v-if="node.type === 'directory' && node.expanded && node.children?.length" class="tree-children" role="group">
                <li v-for="child in node.children" :key="child.path">
                  <div
                    class="tree-node depth-1"
                    :class="{ active: selectedFilePath === child.path, expanded: child.expanded }"
                    role="treeitem"
                    :aria-expanded="child.type === 'directory' ? child.expanded : undefined"
                    :aria-selected="selectedFilePath === child.path"
                    tabindex="0"
                    @click="toggleNode(child)"
                    @keydown.enter="toggleNode(child)"
                    @keydown.space.prevent="toggleNode(child)"
                  >
                    <span v-if="child.type === 'directory'" class="tree-arrow">{{ child.expanded ? '▼' : '▶' }}</span>
                    <span v-else class="tree-arrow-placeholder"></span>
                    <span class="tree-icon">{{ child.type === 'directory' ? '📂' : getFileIcon(child.name) }}</span>
                    <span class="tree-name">{{ child.name }}</span>
                  </div>
                  <ul v-if="child.type === 'directory' && child.expanded && child.children?.length" class="tree-children" role="group">
                    <li v-for="gc in child.children" :key="gc.path">
                      <div
                        class="tree-node depth-2"
                        :class="{ active: selectedFilePath === gc.path }"
                        role="treeitem"
                        :aria-selected="selectedFilePath === gc.path"
                        tabindex="0"
                        @click="toggleNode(gc)"
                        @keydown.enter="toggleNode(gc)"
                        @keydown.space.prevent="toggleNode(gc)"
                      >
                        <span class="tree-arrow-placeholder"></span>
                        <span class="tree-icon">{{ gc.type === 'directory' ? '📂' : getFileIcon(gc.name) }}</span>
                        <span class="tree-name">{{ gc.name }}</span>
                      </div>
                    </li>
                  </ul>
                </li>
              </ul>
            </li>
          </ul>
        </template>
      </div>
    </aside>

    <!-- Main Content -->
    <div class="kb-main">
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
            ref="searchInputRef"
            v-model="query"
            @keyup.enter="search"
            class="search-input"
            placeholder="搜索知识库文章..."
            aria-label="搜索知识库文章"
          >
          <button
            v-if="query"
            class="btn btn-ghost btn-sm clear-btn"
            @click="clearSearch"
            aria-label="清除搜索"
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

      <!-- Sections Error -->
      <div v-if="sectionsError" class="card error-banner" role="alert">
        <span>⚠️ {{ sectionsError }}</span>
        <button class="btn btn-ghost btn-sm" @click="fetchSections">重试</button>
      </div>

      <!-- Sections Overview -->
      <div class="sections-grid">
        <div v-if="loadingSections" class="card section-card loading">
          <SkeletonLoader type="text" width="80%" :count="2" />
        </div>
        <template v-else>
          <div
            v-for="s in sections"
            :key="s.name"
            class="card section-card"
            :class="{ active: selectedSection === s.name }"
            role="button"
            tabindex="0"
            :aria-pressed="selectedSection === s.name"
            @click="selectSection(s.name)"
            @keydown.enter="selectSection(s.name)"
            @keydown.space.prevent="selectSection(s.name)"
          >
            <span class="section-icon">{{ getSectionIcon(s.name) }}</span>
            <div class="section-info">
              <span class="section-name">{{ s.name }}</span>
              <span class="section-count">{{ s.count }} 篇</span>
            </div>
          </div>
        </template>
      </div>

      <!-- File Viewer -->
      <div v-if="selectedFilePath" class="card file-viewer">
        <div class="file-viewer-header">
          <span class="file-viewer-path">📄 {{ selectedFilePath }}</span>
          <button class="btn btn-ghost btn-sm" @click="closeFile">✕ 关闭</button>
        </div>
        <div v-if="fileLoading" class="file-viewer-loading">
          <SkeletonLoader type="text" :count="8" />
        </div>
        <div v-else-if="fileError" class="file-viewer-error">
          ⚠️ {{ fileError }}
        </div>
        <pre v-else class="file-viewer-content">{{ fileContent }}</pre>
      </div>

      <!-- Search Results -->
      <div v-if="searched" class="results-section">
        <!-- Loading Skeletons -->
        <div v-if="loading" class="results-list">
          <div v-for="i in 3" :key="i" class="card result-card-skeleton" style="padding: 16px;">
            <SkeletonLoader type="title" width="60%" />
            <SkeletonLoader type="text" :count="2" />
            <SkeletonLoader type="text" width="30%" />
          </div>
        </div>

        <!-- Results -->
        <template v-else>
          <!-- Search Error -->
          <div v-if="searchError" class="card error-banner" role="alert">
            <span>⚠️ {{ searchError }}</span>
            <button class="btn btn-ghost btn-sm" @click="search">重试</button>
          </div>

          <div class="results-header">
            <span class="results-count">找到 {{ results.length }} 条结果</span>
            <span v-if="selectedSection" class="results-filter">
              筛选: {{ selectedSection }}
              <button class="btn btn-ghost btn-xs" @click="selectedSection = null; search()" aria-label="清除筛选">✕</button>
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
      <div v-if="!searched && !selectedFilePath" class="card initial-state">
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
            <li>左侧目录树可直接浏览文件</li>
          </ul>
        </div>
      </div>

      <!-- Keyboard Shortcuts Hint -->
      <div class="keyboard-hints" role="region" aria-label="快捷键说明">
        <div class="hint-item"><kbd>/</kbd><span>聚焦搜索</span></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kb-layout {
  display: flex;
  gap: var(--space-xl);
  min-height: calc(100vh - 120px);
}

.kb-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2xl);
}

.kb-sidebar {
  width: 268px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: rgba(255, 253, 248, 0.62);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-sm);
}

.sidebar-header {
  padding: var(--space-md) var(--space-lg);
  border-bottom: 1px solid var(--border-light);
  background: rgba(248, 244, 236, 0.68);
}

.sidebar-title {
  font-size: var(--text-md);
  font-weight: 650;
  color: var(--text-primary);
  margin: 0;
}

.tree-container {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-sm);
}

.tree-loading,
.file-viewer-loading {
  padding: var(--space-md);
}

.tree-empty {
  padding: var(--space-lg);
  text-align: center;
  color: var(--text-tertiary);
  font-size: var(--text-sm);
}

.tree-list,
.tree-children {
  list-style: none;
  margin: 0;
  padding: 0;
}

.tree-children { padding-left: var(--space-md); }

.tree-node {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  padding: var(--space-xs) var(--space-sm);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  user-select: none;
}

.tree-node:hover {
  background: rgba(248, 244, 236, 0.68);
  border-color: var(--border-light);
}

.tree-node.active {
  background: var(--primary-light);
  border-color: rgba(77, 100, 117, 0.22);
  color: var(--primary-dark);
}

.tree-node.depth-1 { padding-left: var(--space-md); }
.tree-node.depth-2 { padding-left: var(--space-lg); }

.tree-arrow,
.tree-arrow-placeholder {
  width: 16px;
  flex-shrink: 0;
}

.tree-arrow {
  text-align: center;
  font-size: 10px;
  color: var(--text-tertiary);
}

.tree-icon {
  flex-shrink: 0;
  font-size: var(--text-sm);
  opacity: 0.72;
  filter: grayscale(0.18);
}

.tree-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-viewer {
  overflow: hidden;
  background: var(--surface-glow);
}

.file-viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  background: rgba(248, 244, 236, 0.68);
  border-bottom: 1px solid var(--border-light);
}

.file-viewer-path {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.file-viewer-error {
  padding: var(--space-lg);
  color: var(--danger);
  font-size: var(--text-md);
}

.file-viewer-content {
  padding: var(--space-lg);
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.75;
  color: var(--text-primary);
  background-image: var(--paper-grain);
  background-size: 8px 8px;
  max-height: 600px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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

.search-card {
  padding: var(--space-lg);
  background: var(--surface-glow);
}

.search-input-group {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  background: rgba(248, 244, 236, 0.66);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  padding: var(--space-sm) var(--space-md);
  transition: background var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.search-input-group:focus-within {
  background: var(--bg-card);
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(77, 100, 117, 0.11);
}

.search-icon {
  font-size: var(--text-lg);
  opacity: 0.62;
  filter: grayscale(0.2);
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

.search-input::placeholder { color: var(--text-disabled); }

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
  animation: spin 0.9s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.sections-grid {
  display: flex;
  gap: var(--space-md);
  flex-wrap: wrap;
}

.section-card {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  min-width: 124px;
  padding: var(--space-md) var(--space-lg);
  background: var(--surface-glow);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast), background var(--transition-fast);
}

.section-card.loading {
  cursor: default;
  opacity: 0.7;
}

.section-card:hover {
  background: rgba(255, 253, 248, 0.92);
  border-color: var(--border-color);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.section-card.active {
  background: var(--primary-light);
  border-color: rgba(77, 100, 117, 0.24);
}

.section-icon,
.result-icon,
.initial-icon,
.empty-state-icon {
  opacity: 0.66;
  filter: grayscale(0.18);
}

.section-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: var(--radius-lg);
  background: rgba(248, 244, 236, 0.72);
  font-size: var(--text-xl);
}

.section-info {
  display: flex;
  flex-direction: column;
}

.section-name {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  text-transform: capitalize;
}

.section-count {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

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
  padding: var(--space-xs) var(--space-md);
  background: var(--primary-light);
  border: 1px solid rgba(77, 100, 117, 0.18);
  border-radius: var(--radius-full);
  color: var(--primary-dark);
  font-size: var(--text-sm);
}

.btn-xs {
  padding: 3px 8px;
  font-size: var(--text-xs);
}

.result-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  background: var(--surface-glow);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast);
}

.result-card:hover {
  border-color: var(--border-color);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.result-header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
}

.result-icon {
  font-size: var(--text-xl);
  line-height: 1;
}

.result-info {
  flex: 1;
  min-width: 0;
}

.result-title {
  font-size: var(--text-lg);
  font-weight: 650;
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

.meta-divider { color: var(--text-disabled); }

.result-match {
  padding: var(--space-md);
  background: rgba(248, 244, 236, 0.62);
  border: 1px solid var(--border-light);
  border-left: 3px solid var(--primary);
  border-radius: var(--radius-xl);
}

.match-text {
  font-size: var(--text-md);
  color: var(--text-secondary);
  line-height: 1.7;
}

.match-text :deep(.highlight) {
  background: var(--warning-light);
  color: var(--warning);
  padding: 1px 4px;
  border-radius: 4px;
  font-weight: 600;
}

.empty-state,
.initial-state {
  padding: var(--space-4xl);
  background-image: var(--paper-grain);
  background-size: 8px 8px;
}

.initial-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.initial-icon {
  font-size: 56px;
  margin-bottom: var(--space-lg);
}

.initial-title {
  font-size: var(--text-2xl);
  font-weight: 650;
  color: var(--text-primary);
  margin-bottom: var(--space-sm);
}

.initial-description {
  font-size: var(--text-md);
  color: var(--text-tertiary);
  max-width: 420px;
  margin-bottom: var(--space-2xl);
}

.initial-tips {
  max-width: 380px;
  padding: var(--space-lg);
  background: rgba(248, 244, 236, 0.62);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  text-align: left;
}

.tip-title {
  font-size: var(--text-md);
  font-weight: 650;
  color: var(--text-primary);
  margin-bottom: var(--space-md);
}

.tip-list {
  margin: 0;
  padding-left: var(--space-lg);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.85;
}

.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  padding: var(--space-md) var(--space-lg);
  background: var(--danger-light);
  color: var(--danger);
  font-size: var(--text-md);
  border-left: 3px solid var(--danger);
}

.error-banner .btn { flex-shrink: 0; }

@media (max-width: 768px) {
  .kb-layout { flex-direction: column; }

  .kb-sidebar {
    width: 100%;
    max-height: 220px;
  }

  .sections-grid {
    overflow-x: auto;
    flex-wrap: nowrap;
    padding-bottom: var(--space-sm);
  }

  .section-card { min-width: 112px; }
  .search-input-group { flex-wrap: wrap; }
}
</style>
