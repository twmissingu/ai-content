<script setup lang="ts">
/**
 * PipelineView.vue — slim layout coordinator for the pipeline status page.
 * Extracted sub-components:
 *   - PipelineTriggerPanel (trigger buttons + dialog)
 *   - PipelineStatusCards (timeline, budget, kanban, flywheel)
 *   - PipelineTraceTimeline (execution history)
 */
import { computed, ref, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { useToast } from '../composables/useToast'
import { useKeyboardShortcut, isInputElement } from '../composables/useKeyboardShortcut'
import SkeletonLoader from '../components/SkeletonLoader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import PipelineTriggerPanel from '../components/PipelineTriggerPanel.vue'
import PipelineStatusCards from '../components/PipelineStatusCards.vue'
import PipelineTraceTimeline from '../components/PipelineTraceTimeline.vue'

const store = useDashboardStore()
const toast = useToast()

// ── Quick approval pending review ──────────────────────────────────
const quickApprovingId = ref<string | null>(null)
const quickRejectingId = ref<string | null>(null)
const quickRejectReason = ref('')

const pendingArticles = computed(() => store.approvalQueue.slice(0, 3))

async function quickApprove(id: string) {
  quickApprovingId.value = id
  try {
    await store.approve(id)
    toast.success('已通过')
    await store.fetchApprovalQueue()
  } catch (e) {
    toast.error(`操作失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    quickApprovingId.value = null
  }
}

async function quickReject(id: string) {
  if (!quickRejectReason.value.trim()) return
  quickRejectingId.value = id
  try {
    await store.reject(id, quickRejectReason.value)
    toast.success('已驳回')
    quickRejectReason.value = ''
    quickRejectingId.value = null
    await store.fetchApprovalQueue()
  } catch (e) {
    toast.error(`操作失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    quickRejectingId.value = null
  }
}

// ── Agent helpers ─────────────────────────────────────────────────
const agentList = computed(() =>
  Object.entries(store.agents).map(([name, data]) => ({ name, ...data }))
)

const stageIcons: Record<string, string> = {
  scout: '🔍', writer: '✍️', publisher: '📤', feedback: '📊',
}

const stageNames: Record<string, string> = {
  scout: '选题侦察', writer: '内容写作', publisher: '平台分发', feedback: '数据回收',
}

function getAgentIcon(name: string): string {
  for (const [key, icon] of Object.entries(stageIcons)) {
    if (name.includes(key)) return icon
  }
  return '⚙️'
}

function getAgentLabel(name: string): string {
  for (const [key, label] of Object.entries(stageNames)) {
    if (name.includes(key)) return label
  }
  return name
}

function getProgressColor(pct: number): string {
  if (pct >= 100) return 'success'
  if (pct >= 60) return 'primary'
  return 'warning'
}

// ── Keyboard shortcuts ──────────────────────────────────────────────
function handleKeydown(e: KeyboardEvent) {
  if (isInputElement(e.target)) return
  if (e.key === 'r' || e.key === 'R') {
    store.fetchPipeline()
  }
}

useKeyboardShortcut(handleKeydown)

// ── Lifecycle ────────────────────────────────────────────────────
onMounted(() => {
  store.fetchApprovalQueue()
  store.fetchTraceSessions()
  store.fetchFlywheel()
})
</script>

<template>
  <div class="pipeline-view">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title" id="pipeline-title">管线状态</h2>
        <p class="page-subtitle">实时监控各 Agent 运行状态</p>
      </div>
      <div class="page-actions">
        <PipelineTriggerPanel />
        <button
          class="btn btn-ghost btn-sm"
          aria-label="刷新管线状态"
          @click="store.fetchPipeline()"
        >
          🔄 刷新
        </button>
      </div>
    </div>

    <PipelineStatusCards />
    <PipelineTraceTimeline />

    <!-- Agent Cards Loading Skeletons -->
    <div v-if="store.isLoading('pipeline') && agentList.length === 0" class="agents-grid" role="region" aria-label="加载中">
      <div v-for="i in 4" :key="i" class="card agent-card-skeleton">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
          <SkeletonLoader type="avatar" />
          <div style="flex: 1;">
            <SkeletonLoader type="title" width="60%" />
            <SkeletonLoader type="text" width="40%" />
          </div>
        </div>
        <SkeletonLoader type="text" />
        <SkeletonLoader type="card" height="32px" />
      </div>
    </div>

    <!-- Agent Cards -->
    <div v-else class="agents-grid" role="region" aria-label="Agent 运行状态">
      <div v-for="agent in agentList" :key="agent.name" class="card agent-card">
        <div class="agent-header">
          <div class="agent-info">
            <span class="agent-icon">{{ getAgentIcon(agent.name) }}</span>
            <div>
              <h3 class="agent-name">{{ getAgentLabel(agent.name) }}</h3>
              <span class="agent-worker">{{ agent.name }}</span>
            </div>
          </div>
          <StatusBadge
            :status="agent.stage === 'completed' || agent.progress_pct >= 100 ? 'completed' : agent.error ? 'error' : 'running'"
          />
        </div>

        <div v-if="agent.stage_name" class="agent-stage">
          <span class="stage-label">当前阶段</span>
          <span class="stage-value">{{ agent.stage_name }}</span>
        </div>

        <div class="agent-progress">
          <div
            class="progress-bar"
            role="progressbar"
            :aria-valuenow="agent.progress_pct || 0"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-label="`${getAgentLabel(agent.name)} 进度 ${agent.progress_pct || 0}%`"
          >
            <div
              class="progress-bar-fill"
              :class="getProgressColor(agent.progress_pct || 0)"
              :style="{ width: (agent.progress_pct || 0) + '%' }"
            ></div>
          </div>
          <span class="progress-text">{{ agent.progress_pct || 0 }}%</span>
        </div>

        <div v-if="agent.workers && Object.keys(agent.workers).length > 0" class="sub-workers">
          <div class="sub-workers-header">
            <span class="sub-workers-label">子任务进度</span>
          </div>
          <div class="sub-workers-list">
            <div
              v-for="(worker, workerName) in agent.workers"
              :key="workerName"
              class="sub-worker-item"
              :class="`status-${worker.status}`"
            >
              <span class="sub-worker-name">{{ workerName }}</span>
              <div class="sub-worker-progress">
                <div
                  class="progress-bar progress-bar-sm"
                  role="progressbar"
                  :aria-valuenow="worker.progress_pct || 0"
                  aria-valuemin="0"
                  aria-valuemax="100"
                  :aria-label="`${workerName} 进度 ${worker.progress_pct || 0}%`"
                >
                  <div
                    class="progress-bar-fill"
                    :class="worker.status === 'completed' ? 'success' : worker.status === 'failed' ? 'danger' : 'primary'"
                    :style="{ width: (worker.progress_pct || 0) + '%' }"
                  ></div>
                </div>
                <span class="sub-worker-pct">{{ worker.progress_pct || 0 }}%</span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="agent.detail" class="agent-detail">{{ agent.detail }}</div>

        <div v-if="agent.timeout" class="agent-alert alert-warning">
          ⚠️ 运行超时
        </div>
        <div v-if="agent.error" class="agent-alert alert-danger">
          <span class="alert-message">❌ {{ agent.error }}</span>
        </div>
      </div>
    </div>

    <!-- Pending Review Section -->
    <div v-if="pendingArticles.length > 0" class="card pending-review-card" role="region" aria-label="待审批内容">
      <div class="card-header">
        <h3 class="card-title">📝 待审批内容</h3>
        <router-link to="/approval" class="view-all-link">查看全部 →</router-link>
      </div>
      <div class="pending-list">
        <div v-for="article in pendingArticles" :key="article.id" class="pending-item">
          <div class="pending-info">
            <h4 class="pending-title">{{ article.meta.topic || '未知选题' }}</h4>
            <div class="pending-meta">
              <span class="meta-tag">📊 {{ article.meta.proofread_score || '-' }}分</span>
              <span class="meta-tag">📝 {{ article.meta.word_count || 0 }}字</span>
              <span v-if="article.meta.platform" class="meta-tag">📱 {{ article.meta.platform }}</span>
            </div>
          </div>
          <div class="pending-actions">
            <template v-if="quickRejectingId === article.id">
              <input
                v-model="quickRejectReason"
                class="input reject-reason-input"
                placeholder="驳回原因..."
                aria-label="驳回原因"
                @keyup.enter="quickReject(article.id)"
              />
              <button
                class="btn btn-danger btn-xs"
                :disabled="!quickRejectReason.trim()"
                aria-label="确认驳回"
                @click="quickReject(article.id)"
              >确认</button>
              <button
                class="btn btn-ghost btn-xs"
                aria-label="取消驳回"
                @click="quickRejectingId = null; quickRejectReason = ''"
              >取消</button>
            </template>
            <template v-else>
              <button
                class="btn btn-success btn-xs"
                :disabled="quickApprovingId === article.id"
                aria-label="快速通过"
                @click="quickApprove(article.id)"
              >{{ quickApprovingId === article.id ? '...' : '✅ 通过' }}</button>
              <button
                class="btn btn-danger btn-xs"
                :disabled="quickRejectingId !== null"
                aria-label="快速驳回"
                @click="quickRejectingId = article.id"
              >❌ 驳回</button>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="agentList.length === 0 && pendingArticles.length === 0" class="card empty-state" role="region" aria-label="系统空闲">
      <div class="empty-state-animation">
        <div class="empty-state-icon">🤖</div>
        <div class="empty-state-pulse"></div>
      </div>
      <div class="empty-state-title">系统空闲</div>
      <div class="empty-state-description">等待下一时段的 Scout 选题任务</div>
      <div class="empty-state-action">
        <button class="btn btn-primary" aria-label="检查管线状态" @click="store.fetchPipeline()">
          🔄 检查状态
        </button>
      </div>
    </div>

    <!-- Keyboard Shortcuts Hint -->
    <div class="keyboard-hints" role="region" aria-label="快捷键说明">
      <div class="hint-item"><kbd>R</kbd><span>刷新</span></div>
    </div>
  </div>
</template>

<style scoped>
.pipeline-view { display: flex; flex-direction: column; gap: var(--space-2xl); }

/* ── Page Header ─────────────────────────────────────────────── */
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
  font-weight: 720;
  color: var(--text-primary);
  margin: 0 0 var(--space-xs) 0;
  letter-spacing: 0.04em;
}
.page-subtitle { font-size: var(--text-md); color: var(--text-tertiary); margin: 0; }
.page-actions { display: flex; gap: var(--space-sm); flex-shrink: 0; }

@media (max-width: 768px) {
  .page-header { flex-direction: column; gap: var(--space-md); }
  .page-actions { width: 100%; justify-content: flex-end; }
}

/* ── Agent Cards Grid ────────────────────────────────────────── */
.agents-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr)); gap: var(--space-lg); }
.agent-card { display: flex; flex-direction: column; gap: var(--space-lg); transition: border-color var(--transition-normal), box-shadow var(--transition-normal), transform var(--transition-normal); }
.agent-card:hover { border-color: var(--border-color); box-shadow: var(--shadow-md); transform: translateY(-1px); }

.agent-header { display: flex; justify-content: space-between; align-items: flex-start; }
.agent-info { display: flex; align-items: center; gap: var(--space-md); }
.agent-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  font-size: var(--text-2xl);
  line-height: 1;
  border-radius: var(--radius-xl);
  background: var(--bg-secondary);
  opacity: 0.76;
  filter: grayscale(0.18);
}
.agent-name { font-size: var(--text-xl); font-weight: 680; color: var(--text-primary); margin: 0; letter-spacing: 0.01em; }
.agent-worker { font-size: var(--text-xs); color: var(--text-disabled); font-family: var(--font-mono); margin-top: 2px; display: block; }

.agent-stage { display: inline-flex; align-items: center; gap: var(--space-sm); padding: var(--space-xs) var(--space-md); background: var(--primary-light); border: 1px solid rgba(77, 100, 117, 0.12); border-radius: var(--radius-full); align-self: flex-start; }
.stage-label { font-size: var(--text-xs); color: var(--primary); font-weight: 560; }
.stage-value { font-size: var(--text-xs); font-weight: 650; color: var(--primary-dark); }

.agent-progress { display: flex; align-items: center; gap: var(--space-md); }
.agent-progress .progress-bar { flex: 1; }
.progress-text { font-size: var(--text-sm); font-weight: 650; color: var(--text-secondary); min-width: 40px; text-align: right; font-family: var(--font-mono); }

.agent-detail { font-size: var(--text-sm); color: var(--text-secondary); padding: var(--space-md); background: rgba(250, 247, 240, 0.72); border-radius: var(--radius-lg); border-left: 2px solid var(--accent-line); }

.agent-alert { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm) var(--space-md); border-radius: var(--radius-lg); font-size: var(--text-sm); font-weight: 560; }
.alert-warning { background: var(--warning-light); color: var(--warning-dark); }
.alert-danger { background: var(--danger-light); color: var(--danger); }
.alert-message { flex: 1; }

.sub-workers { border-top: 1px solid var(--divider); padding-top: var(--space-md); }
.sub-workers-header { margin-bottom: var(--space-sm); }
.sub-workers-label { font-size: var(--text-xs); color: var(--text-tertiary); font-weight: 560; letter-spacing: 0.04em; }
.sub-workers-list { display: flex; flex-direction: column; gap: var(--space-xs); }

.sub-worker-item { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm); background: rgba(250, 247, 240, 0.76); border-radius: var(--radius-md); border-left: 2px solid var(--border-color); }
.sub-worker-item.status-completed { border-left-color: var(--success); }
.sub-worker-item.status-running { border-left-color: var(--primary); }
.sub-worker-item.status-failed { border-left-color: var(--danger); }
.sub-worker-name { font-size: var(--text-xs); color: var(--text-secondary); min-width: 80px; }
.sub-worker-progress { flex: 1; display: flex; align-items: center; gap: var(--space-sm); }
.progress-bar-sm { height: 4px; }
.sub-worker-pct { font-size: var(--text-xs); color: var(--text-tertiary); min-width: 32px; text-align: right; font-family: var(--font-mono); }

/* ── Empty State ─────────────────────────────────────────────── */
.empty-state { padding: var(--space-4xl); text-align: center; }
.empty-state-animation { position: relative; display: inline-block; margin-bottom: var(--space-lg); }
.empty-state-icon { font-size: 52px; position: relative; z-index: 1; opacity: 0.45; filter: grayscale(0.22); }
.empty-state-pulse { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 86px; height: 86px; border-radius: 50%; background: var(--primary-light); animation: pulse 2.8s infinite; z-index: 0; }
.empty-state-title { font-size: var(--text-2xl); font-weight: 650; color: var(--text-primary); margin-bottom: var(--space-sm); }
.empty-state-description { font-size: var(--text-md); color: var(--text-tertiary); margin-bottom: var(--space-xl); }
.empty-state-action { display: flex; justify-content: center; }

/* ── Pending Review Card ─────────────────────────────────────── */
.pending-review-card { border-left: 3px solid var(--warning); }
.pending-review-card .card-header { display: flex; justify-content: space-between; align-items: center; }
.view-all-link { font-size: var(--text-sm); color: var(--primary); text-decoration: none; font-weight: 560; }
.view-all-link:hover { color: var(--primary-hover); }
.pending-list { display: flex; flex-direction: column; gap: var(--space-md); }
.pending-item { display: flex; justify-content: space-between; align-items: center; gap: var(--space-lg); padding: var(--space-lg); background: rgba(250, 247, 240, 0.82); border: 1px solid var(--border-light); border-radius: var(--radius-lg); transition: background var(--transition-fast), border-color var(--transition-fast); }
.pending-item:hover { background: var(--bg-hover); border-color: var(--border-color); }
.pending-info { flex: 1; min-width: 0; }
.pending-title { font-size: var(--text-md); font-weight: 650; color: var(--text-primary); margin: 0 0 var(--space-xs) 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pending-meta { display: flex; gap: var(--space-sm); flex-wrap: wrap; }
.meta-tag { font-size: var(--text-xs); color: var(--text-tertiary); background: var(--bg-card); border: 1px solid var(--border-light); padding: 2px 8px; border-radius: var(--radius-full); }
.pending-actions { display: flex; gap: var(--space-sm); align-items: center; flex-shrink: 0; }
.reject-reason-input { width: 150px; padding: 4px 8px; font-size: var(--text-sm); }
.btn-xs { min-height: 28px; padding: 3px 9px; font-size: var(--text-xs); }

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .agents-grid { grid-template-columns: 1fr; }
  .pending-item { flex-direction: column; align-items: flex-start; }
  .pending-actions { width: 100%; justify-content: flex-end; }
}


</style>
