<script setup lang="ts">
import { ref, onMounted } from 'vue'
import SkeletonLoader from '../components/SkeletonLoader.vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

interface PromptTemplate {
  name: string
  version: number
  template: string
  variables: string[]
  is_active: boolean
  created_at: string
}

interface PromptVersion {
  name: string
  version: number
  template: string
  variables: string[]
  is_active: boolean
  created_at: string
}

const prompts = ref<PromptTemplate[]>([])
const loading = ref(false)
const selectedPrompt = ref<PromptTemplate | null>(null)
const versions = ref<PromptVersion[]>([])
const editingTemplate = ref('')
const editingName = ref('')
const showEditor = ref(false)
const saving = ref(false)
const importing = ref(false)

async function fetchPrompts() {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/prompts`)
    const data = await res.json()
    prompts.value = data.prompts || []
  } catch (e) {
    console.error('Failed to fetch prompts:', e)
  } finally {
    loading.value = false
  }
}

async function selectPrompt(prompt: PromptTemplate) {
  selectedPrompt.value = prompt
  editingTemplate.value = prompt.template
  editingName.value = prompt.name
  showEditor.value = true

  // Fetch version history
  try {
    const res = await fetch(`${API_BASE}/api/prompts/${prompt.name}/versions`)
    const data = await res.json()
    versions.value = data.versions || []
  } catch (e) {
    versions.value = []
  }
}

async function savePrompt() {
  if (!editingName.value || !editingTemplate.value) return
  saving.value = true
  try {
    const variables = [...editingTemplate.value.matchAll(/\{(\w+)\}/g)].map(m => m[1])
    const res = await fetch(`${API_BASE}/api/prompts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: editingName.value,
        template: editingTemplate.value,
        variables,
      }),
    })
    if (res.ok) {
      await fetchPrompts()
      // Refresh versions
      const vRes = await fetch(`${API_BASE}/api/prompts/${editingName.value}/versions`)
      const vData = await vRes.json()
      versions.value = vData.versions || []
    }
  } catch (e) {
    console.error('Failed to save prompt:', e)
  } finally {
    saving.value = false
  }
}

async function rollbackVersion(name: string, version: number) {
  try {
    const res = await fetch(`${API_BASE}/api/prompts/${name}/activate?version=${version}`, {
      method: 'POST',
    })
    if (res.ok) {
      await fetchPrompts()
      // Refresh versions
      const vRes = await fetch(`${API_BASE}/api/prompts/${name}/versions`)
      const vData = await vRes.json()
      versions.value = vData.versions || []
      // Reload the active prompt template
      const pRes = await fetch(`${API_BASE}/api/prompts/${name}`)
      if (pRes.ok) {
        const pData = await pRes.json()
        editingTemplate.value = pData.template
        selectedPrompt.value = pData
      }
    }
  } catch (e) {
    console.error('Failed to rollback:', e)
  }
}

async function importFromFiles() {
  importing.value = true
  try {
    const res = await fetch(`${API_BASE}/api/prompts/import`, { method: 'POST' })
    if (res.ok) {
      await fetchPrompts()
    }
  } catch (e) {
    console.error('Failed to import:', e)
  } finally {
    importing.value = false
  }
}

function closeEditor() {
  showEditor.value = false
  selectedPrompt.value = null
  editingTemplate.value = ''
}

onMounted(fetchPrompts)
</script>

<template>
  <div class="config-view">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title">系统配置</h2>
        <p class="page-subtitle">管理提示词模板、系统参数</p>
      </div>
      <button class="btn btn-ghost" @click="importFromFiles" :disabled="importing">
        {{ importing ? '导入中...' : '从文件导入' }}
      </button>
    </div>

    <!-- Prompt List -->
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">提示词模板</h3>
        <span class="card-count">{{ prompts.length }} 个模板</span>
      </div>

      <div v-if="loading" class="prompt-list">
        <div v-for="i in 3" :key="i" class="prompt-item-skeleton">
          <SkeletonLoader type="text" width="40%" />
          <SkeletonLoader type="text" width="20%" />
        </div>
      </div>

      <div v-else-if="prompts.length === 0" class="empty-state">
        <div class="empty-icon">📝</div>
        <div class="empty-text">暂无提示词模板</div>
        <button class="btn btn-primary btn-sm" @click="importFromFiles" :disabled="importing">
          从 config/prompts/ 导入
        </button>
      </div>

      <div v-else class="prompt-list">
        <div
          v-for="p in prompts"
          :key="p.name"
          class="prompt-item"
          :class="{ active: selectedPrompt?.name === p.name }"
          @click="selectPrompt(p)"
          role="button"
          tabindex="0"
          @keydown.enter="selectPrompt(p)"
        >
          <div class="prompt-info">
            <span class="prompt-name">{{ p.name }}</span>
            <span class="prompt-meta">
              v{{ p.version }} · {{ p.variables.length }} 个变量 · {{ p.created_at?.split('T')[0] }}
            </span>
          </div>
          <span class="prompt-badge">v{{ p.version }}</span>
        </div>
      </div>
    </div>

    <!-- Editor Panel -->
    <transition name="slide">
      <div v-if="showEditor && selectedPrompt" class="card editor-card">
        <div class="editor-header">
          <div>
            <h3 class="editor-title">{{ editingName }}</h3>
            <span class="editor-meta">
              v{{ selectedPrompt.version }} · 变量: {{ selectedPrompt.variables.join(', ') || '无' }}
            </span>
          </div>
          <button class="btn btn-ghost btn-sm" @click="closeEditor">✕</button>
        </div>

        <textarea
          v-model="editingTemplate"
          class="prompt-textarea"
          rows="16"
          spellcheck="false"
          aria-label="提示词模板内容"
        ></textarea>

        <div class="editor-actions">
          <button class="btn btn-primary" @click="savePrompt" :disabled="saving">
            {{ saving ? '保存中...' : '保存新版本' }}
          </button>
        </div>

        <!-- Version History -->
        <div v-if="versions.length > 1" class="version-history">
          <h4 class="version-title">版本历史</h4>
          <div class="version-list">
            <div
              v-for="v in versions"
              :key="v.version"
              class="version-item"
              :class="{ active: v.is_active }"
            >
              <div class="version-info">
                <span class="version-num">v{{ v.version }}</span>
                <span class="version-date">{{ v.created_at?.split('T')[0] }}</span>
                <span v-if="v.is_active" class="version-active">当前</span>
              </div>
              <button
                v-if="!v.is_active"
                class="btn btn-ghost btn-xs"
                @click="rollbackVersion(v.name, v.version)"
              >
                回滚
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.config-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-lg);
}

.card-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.card-count {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

.prompt-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.prompt-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.prompt-item:hover {
  background: var(--bg-hover);
}

.prompt-item.active {
  background: var(--primary-light);
  border: 1px solid var(--primary);
}

.prompt-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.prompt-name {
  font-weight: 500;
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.prompt-meta {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

.prompt-badge {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-light);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.prompt-item-skeleton {
  display: flex;
  justify-content: space-between;
  padding: var(--space-md) var(--space-lg);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-2xl);
  color: var(--text-tertiary);
}

.empty-icon {
  font-size: 48px;
  opacity: 0.5;
}

.empty-text {
  font-size: var(--text-md);
}

.editor-card {
  border: 1px solid var(--primary);
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-lg);
}

.editor-title {
  font-size: var(--text-lg);
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--text-primary);
  margin: 0 0 var(--space-xs) 0;
}

.editor-meta {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

.prompt-textarea {
  width: 100%;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.6;
  padding: var(--space-md);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  color: var(--text-primary);
  resize: vertical;
  outline: none;
  transition: border-color var(--transition-fast);
}

.prompt-textarea:focus {
  border-color: var(--primary);
}

.editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-md);
  margin-top: var(--space-md);
}

.version-history {
  margin-top: var(--space-xl);
  padding-top: var(--space-lg);
  border-top: 1px solid var(--border-light);
}

.version-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-md) 0;
}

.version-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.version-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}

.version-item.active {
  background: var(--success-light);
}

.version-info {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.version-num {
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.version-date {
  color: var(--text-tertiary);
}

.version-active {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--success);
  background: var(--success-light);
  padding: 1px 6px;
  border-radius: var(--radius-full);
}

.btn-xs {
  padding: 2px 6px;
  font-size: var(--text-xs);
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: var(--space-md);
  }
}
</style>
