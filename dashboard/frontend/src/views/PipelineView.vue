<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { useToast } from '../composables/useToast'
import StatusBadge from '../components/StatusBadge.vue'
import SkeletonLoader from '../components/SkeletonLoader.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const store = useDashboardStore()
const toast = useToast()

// Quick approval state
const quickApprovingId = ref<string | null>(null)
const quickRejectingId = ref<string | null>(null)
const quickRejectReason = ref('')

// Pending review articles (from approval queue, show top 3)
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

const agentList = computed(() => {
  const entries = Object.entries(store.agents)
  return entries.map(([name, data]) => ({
    name,
    ...data,
  }))
})

const agents = computed(() => store.agents as Record<string, any>)

const kanbanCounts = computed(() => {
  const agentData = store.agents
  const scoutRunning = agentData.scout && agentData.scout.progress_pct < 100 && !agentData.scout.error
  const writerRunning = agentData.writer && agentData.writer.progress_pct < 100 && !agentData.writer.error
  const publisherRunning = agentData.publisher && agentData.publisher.progress_pct < 100 && !agentData.publisher.error

  return {
    discovering: scoutRunning ? 1 : 0,
    writing: writerRunning ? 1 : 0,
    pending: store.approvalQueue.length,
    published: publisherRunning ? 1 : 0,
  }
})

const stageNames: Record<string, string> = {
  scout: '选题侦察',
  writer: '内容写作',
  publisher: '平台分发',
  feedback: '数据回收',
}

const stageIcons: Record<string, string> = {
  scout: '🔍',
  writer: '✍️',
  publisher: '📤',
  feedback: '📊',
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
  if (pct >= 80) return 'danger'
  if (pct >= 60) return 'warning'
  return 'primary'
}

// Manual agent trigger
const showTriggerDialog = ref(false)
const triggerTarget = ref<string>('')
const triggerLoading = ref(false)

function openTriggerDialog(agent: string) {
  triggerTarget.value = agent
  showTriggerDialog.value = true
}

async function confirmTrigger() {
  triggerLoading.value = true
  try {
    const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
    const res = await fetch(`${API_BASE}/api/pipeline/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent: triggerTarget.value }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    toast.success(`${triggerTarget.value === 'scout' ? 'Scout 选题' : 'Writer 写作'}已触发`)
    await store.fetchPipeline()
  } catch (e) {
    toast.error(`触发失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    triggerLoading.value = false
    showTriggerDialog.value = false
  }
}

// Current time with auto-refresh
const currentTime = ref(new Date())
let timeInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  timeInterval = setInterval(() => {
    currentTime.value = new Date()
  }, 60000) // Update every minute
  // Fetch approval queue for pending review section
  store.fetchApprovalQueue()
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
    timeInterval = null
  }
})

const formattedTime = computed(() => {
  return currentTime.value.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
})

// Timeline items from config (with fallback defaults)
const timelineItems = computed(() => {
  const schedule = store.config?.schedule
  if (!schedule) {
    // Fallback defaults
    return [
      { time: '09:00', label: 'Scout 选题', hour: 9, minute: 0 },
      { time: '09:30', label: '人工确认', hour: 9, minute: 30 },
      { time: '09:30', label: 'Writer 写作', hour: 9, minute: 30 },
      { time: '10:45', label: '审批', hour: 10, minute: 45 },
      { time: '11:00', label: '分发', hour: 11, minute: 0 },
    ]
  }
  
  // Parse schedule times
  const parseTime = (timeStr: string) => {
    const [h, m] = timeStr.split(':').map(Number)
    return { hour: h, minute: m }
  }
  
  const morning = parseTime(schedule.morning_scout || '09:00')
  const morningWriter = parseTime(schedule.morning_writer || '09:30')
  const evening = parseTime(schedule.evening_scout || '14:00')
  const eveningWriter = parseTime(schedule.evening_writer || '14:30')
  
  return [
    { time: schedule.morning_scout || '09:00', label: 'Scout 选题 (早)', ...morning },
    { time: schedule.morning_writer || '09:30', label: 'Writer 写作 (早)', ...morningWriter },
    { time: schedule.evening_scout || '14:00', label: 'Scout 选题 (晚)', ...evening },
    { time: schedule.evening_writer || '14:30', label: 'Writer 写作 (晚)', ...eveningWriter },
  ]
})

function getTimelineStatus(item: { hour: number, minute: number }): 'completed' | 'active' | 'pending' {
  const now = currentTime.value
  const currentHour = now.getHours()
  const currentMinute = now.getMinutes()
  const itemMinutes = item.hour * 60 + item.minute
  const currentMinutes = currentHour * 60 + currentMinute
  
  if (currentMinutes >= itemMinutes + 30) return 'completed'
  if (currentMinutes >= itemMinutes) return 'active'
  return 'pending'
}
</script>

<template>
  <div class="pipeline-view">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title">管线状态</h2>
        <p class="page-subtitle">实时监控各 Agent 运行状态</p>
      </div>
      <div class="page-actions">
        <button class="btn btn-primary btn-sm" @click="openTriggerDialog('scout')">
          🔍 执行选题
        </button>
        <button class="btn btn-primary btn-sm" @click="openTriggerDialog('writer')">
          ✍️ 执行写作
        </button>
        <button class="btn btn-ghost btn-sm" @click="store.fetchPipeline()">
          🔄 刷新
        </button>
      </div>
    </div>

    <!-- Trigger Confirmation Dialog -->
    <ConfirmDialog
      v-model:show="showTriggerDialog"
      title="手动触发"
      :message="`确定要立即执行${triggerTarget === 'scout' ? 'Scout 选题' : 'Writer 写作'}吗？`"
      confirmText="立即执行"
      :loading="triggerLoading"
      @confirm="confirmTrigger"
    />

    <!-- Timeline -->
    <div class="card timeline-card">
      <div class="card-header">
        <h3 class="card-title">📅 今日时间线</h3>
        <span class="timeline-current-time">
          当前时间: {{ formattedTime }}
        </span>
      </div>
      <div class="timeline">
        <template v-for="(item, index) in timelineItems" :key="item.time + item.label">
          <div class="timeline-item" :class="getTimelineStatus(item)">
            <span class="timeline-time">{{ item.time }}</span>
            <span class="timeline-dot">
              <span v-if="getTimelineStatus(item) === 'completed'" class="dot-icon">✓</span>
              <span v-else-if="getTimelineStatus(item) === 'active'" class="dot-pulse"></span>
            </span>
            <span class="timeline-label">{{ item.label }}</span>
          </div>
          <div 
            v-if="index < timelineItems.length - 1" 
            class="timeline-connector"
            :class="{ completed: getTimelineStatus(item) === 'completed' }"
          ></div>
        </template>
      </div>
    </div>

    <!-- Budget Status -->
    <div v-if="store.budget" class="card budget-card">
      <div class="card-header">
        <h3 class="card-title">💰 本月成本</h3>
        <StatusBadge 
          :status="store.budget.is_exceeded ? 'error' : store.budget.is_warning ? 'warning' : 'completed'" 
        />
      </div>
      <div class="budget-stats">
        <div class="budget-amount">
          ${{ store.budget.current_cost?.toFixed(2) || '0.00' }}
          <span class="budget-separator">/</span>
          <span class="budget-limit">${{ store.budget.budget?.toFixed(2) || '15.00' }}</span>
        </div>
        <div class="progress-bar">
          <div 
            class="progress-bar-fill"
            :class="{
              success: (store.budget.percentage || 0) < 60,
              warning: (store.budget.percentage || 0) >= 60 && (store.budget.percentage || 0) < 80,
              danger: (store.budget.percentage || 0) >= 80
            }"
            :style="{ width: Math.min(store.budget.percentage || 0, 100) + '%' }"
          ></div>
        </div>
        <div class="budget-percentage">
          {{ store.budget.percentage?.toFixed(1) || '0' }}% 已使用
        </div>
      </div>
    </div>

    <!-- Content Pipeline Kanban -->
    <div class="card pipeline-kanban-card">
      <div class="card-header">
        <h3 class="card-title">📋 内容流转</h3>
        <span class="kanban-hint">实时显示内容在管线中的位置</span>
      </div>
      <div class="kanban-board">
        <div class="kanban-column">
          <div class="kanban-column-header">
            <span class="kanban-column-icon">🔍</span>
            <span class="kanban-column-title">选题中</span>
            <span class="kanban-column-count">{{ kanbanCounts.discovering }}</span>
          </div>
          <div class="kanban-cards">
            <div v-if="kanbanCounts.discovering === 0" class="kanban-empty">空闲</div>
            <div v-else class="kanban-card kanban-active">
              <div class="kanban-card-title">Scout 运行中...</div>
              <div class="kanban-card-detail">{{ agents.scout?.detail || '扫描热门话题' }}</div>
            </div>
          </div>
        </div>
        <div class="kanban-connector">
          <span class="connector-arrow">→</span>
        </div>
        <div class="kanban-column">
          <div class="kanban-column-header">
            <span class="kanban-column-icon">✍️</span>
            <span class="kanban-column-title">写作中</span>
            <span class="kanban-column-count">{{ kanbanCounts.writing }}</span>
          </div>
          <div class="kanban-cards">
            <div v-if="kanbanCounts.writing === 0" class="kanban-empty">空闲</div>
            <div v-else class="kanban-card kanban-active">
              <div class="kanban-card-title">Writer 运行中...</div>
              <div class="kanban-card-detail">{{ agents.writer?.detail || '7阶段管线' }}</div>
            </div>
          </div>
        </div>
        <div class="kanban-connector">
          <span class="connector-arrow">→</span>
        </div>
        <div class="kanban-column">
          <div class="kanban-column-header">
            <span class="kanban-column-icon">📋</span>
            <span class="kanban-column-title">待审批</span>
            <span class="kanban-column-count" :class="{ 'has-items': store.approvalQueue.length > 0 }">
              {{ store.approvalQueue.length }}
            </span>
          </div>
          <div class="kanban-cards">
            <div v-if="store.approvalQueue.length === 0" class="kanban-empty">暂无</div>
            <div
              v-for="article in store.approvalQueue.slice(0, 3)"
              :key="article.id"
              class="kanban-card"
              @click="$router.push('/approval')"
            >
              <div class="kanban-card-title">{{ article.meta.topic || '未知选题' }}</div>
              <div class="kanban-card-meta">
                <span>📊 {{ article.meta.proofread_score || '-' }}分</span>
                <span>📝 {{ article.meta.word_count || 0 }}字</span>
              </div>
            </div>
            <div v-if="store.approvalQueue.length > 3" class="kanban-more">
              +{{ store.approvalQueue.length - 3 }} 更多
            </div>
          </div>
        </div>
        <div class="kanban-connector">
          <span class="connector-arrow">→</span>
        </div>
        <div class="kanban-column">
          <div class="kanban-column-header">
            <span class="kanban-column-icon">📤</span>
            <span class="kanban-column-title">已分发</span>
            <span class="kanban-column-count">{{ kanbanCounts.published }}</span>
          </div>
          <div class="kanban-cards">
            <div v-if="kanbanCounts.published === 0" class="kanban-empty">暂无</div>
            <div v-else class="kanban-card kanban-success">
              <div class="kanban-card-title">今日已发布</div>
              <div class="kanban-card-detail">{{ kanbanCounts.published }} 篇文章</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Agent Cards Loading Skeletons -->
    <div v-if="store.isLoading('pipeline') && agentList.length === 0" class="agents-grid">
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
    <div v-else class="agents-grid">
      <div v-for="agent in agentList" :key="agent.name" class="card agent-card">
        <div class="agent-header">
          <div class="agent-info">
            <span class="agent-icon">{{ getAgentIcon(agent.name) }}</span>
            <div>
              <h3 class="agent-name">{{ getAgentLabel(agent.name) }}</h3>
              <span class="agent-worker">{{ agent.name }}</span>
            </div>
          </div>
          <StatusBadge :status="agent.stage === 'completed' || agent.progress_pct >= 100 ? 'completed' : agent.error ? 'error' : 'running'" />
        </div>

        <!-- Stage Info -->
        <div v-if="agent.stage_name" class="agent-stage">
          <span class="stage-label">当前阶段</span>
          <span class="stage-value">{{ agent.stage_name }}</span>
        </div>

        <!-- Progress Bar -->
        <div class="agent-progress">
          <div class="progress-bar">
            <div
              class="progress-bar-fill"
              :class="getProgressColor(agent.progress_pct || 0)"
              :style="{ width: (agent.progress_pct || 0) + '%' }"
            ></div>
          </div>
          <span class="progress-text">{{ agent.progress_pct || 0 }}%</span>
        </div>

        <!-- Sub-workers (for Writer with multiple stages) -->
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
                <div class="progress-bar progress-bar-sm">
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

        <!-- Detail -->
        <div v-if="agent.detail" class="agent-detail">
          {{ agent.detail }}
        </div>

        <!-- Alerts -->
        <div v-if="agent.timeout" class="agent-alert alert-warning">
          ⚠️ 运行超时
        </div>
        <div v-if="agent.error" class="agent-alert alert-danger">
          <span class="alert-message">❌ {{ agent.error }}</span>
          <button
            class="btn btn-ghost btn-xs retry-btn"
            @click="openTriggerDialog(agent.name)"
          >
            🔄 重试
          </button>
        </div>
      </div>
    </div>

    <!-- Pending Review Section -->
    <div v-if="pendingArticles.length > 0" class="card pending-review-card">
      <div class="card-header">
        <h3 class="card-title">📝 待审批内容</h3>
        <a href="/approval" class="view-all-link">查看全部 →</a>
      </div>
      <div class="pending-list">
        <div
          v-for="article in pendingArticles"
          :key="article.id"
          class="pending-item"
        >
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
                @keyup.enter="quickReject(article.id)"
              />
              <button
                class="btn btn-danger btn-xs"
                :disabled="!quickRejectReason.trim()"
                @click="quickReject(article.id)"
              >
                确认
              </button>
              <button
                class="btn btn-ghost btn-xs"
                @click="quickRejectingId = null; quickRejectReason = ''"
              >
                取消
              </button>
            </template>
            <template v-else>
              <button
                class="btn btn-success btn-xs"
                :disabled="quickApprovingId === article.id"
                @click="quickApprove(article.id)"
              >
                {{ quickApprovingId === article.id ? '...' : '✅ 通过' }}
              </button>
              <button
                class="btn btn-danger btn-xs"
                :disabled="quickRejectingId !== null"
                @click="quickRejectingId = article.id"
              >
                ❌ 驳回
              </button>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="agentList.length === 0 && pendingArticles.length === 0" class="card empty-state">
      <div class="empty-state-animation">
        <div class="empty-state-icon">🤖</div>
        <div class="empty-state-pulse"></div>
      </div>
      <div class="empty-state-title">系统空闲</div>
      <div class="empty-state-description">
        等待下一时段的 Scout 选题任务
      </div>
      <div class="empty-state-action">
        <button class="btn btn-primary" @click="store.fetchPipeline()">
          🔄 检查状态
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pipeline-view {
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

.page-actions {
  display: flex;
  gap: var(--space-sm);
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: var(--space-md);
  }

  .page-actions {
    width: 100%;
    justify-content: flex-end;
  }
}

/* ── Timeline ────────────────────────────────────────────────── */
.timeline-card {
  overflow: hidden;
}

.timeline-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.timeline-current-time {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  font-weight: 500;
}

.timeline {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  overflow-x: auto;
  padding-bottom: var(--space-sm);
}

.timeline-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-xs);
  min-width: 80px;
}

.timeline-item.completed .timeline-time {
  color: var(--success);
}

.timeline-item.active .timeline-time {
  color: var(--primary);
  font-weight: 700;
}

.timeline-time {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.timeline-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 2px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}

.timeline-item.completed .timeline-dot {
  background: var(--success);
  border-color: var(--success);
  color: white;
}

.timeline-item.active .timeline-dot {
  background: var(--primary);
  border-color: var(--primary);
  box-shadow: 0 0 0 4px var(--primary-light);
  animation: pulse 2s infinite;
}

.dot-icon {
  font-size: 12px;
  font-weight: 700;
}

.dot-pulse {
  width: 8px;
  height: 8px;
  background: white;
  border-radius: 50%;
}

.timeline-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}

.timeline-item.completed .timeline-label {
  color: var(--success);
}

.timeline-item.active .timeline-label {
  color: var(--primary);
  font-weight: 600;
}

.timeline-connector {
  flex: 1;
  height: 2px;
  background: var(--border-color);
  min-width: 20px;
  transition: background var(--transition-fast);
}

.timeline-connector.completed {
  background: var(--success);
}

/* ── Budget Card ─────────────────────────────────────────────── */
.budget-card {
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--primary-light) 100%);
}

.budget-stats {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.budget-amount {
  font-size: var(--text-4xl);
  font-weight: 700;
  color: var(--text-primary);
}

.budget-separator {
  color: var(--text-tertiary);
  margin: 0 var(--space-sm);
}

.budget-limit {
  font-size: var(--text-xl);
  font-weight: 400;
  color: var(--text-tertiary);
}

.budget-percentage {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

/* ── Content Pipeline Kanban ─────────────────────────────────── */
.pipeline-kanban-card {
  overflow: hidden;
}

.pipeline-kanban-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kanban-hint {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.kanban-board {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  overflow-x: auto;
  padding-bottom: var(--space-sm);
}

.kanban-column {
  flex: 1;
  min-width: 160px;
  background: var(--bg-hover);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
}

.kanban-column-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--divider);
}

.kanban-column-icon {
  font-size: var(--text-lg);
}

.kanban-column-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.kanban-column-count {
  font-size: var(--text-xs);
  font-weight: 600;
  background: var(--bg-card);
  color: var(--text-secondary);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  min-width: 20px;
  text-align: center;
}

.kanban-column-count.has-items {
  background: var(--warning);
  color: white;
}

.kanban-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.kanban-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.kanban-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.kanban-card.kanban-active {
  border-left: 3px solid var(--primary);
  background: var(--primary-light);
}

.kanban-card.kanban-success {
  border-left: 3px solid var(--success);
  background: var(--success-light);
}

.kanban-card-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kanban-card-detail,
.kanban-card-meta {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
  display: flex;
  gap: var(--space-sm);
}

.kanban-empty {
  font-size: var(--text-xs);
  color: var(--text-disabled);
  text-align: center;
  padding: var(--space-md);
}

.kanban-more {
  font-size: var(--text-xs);
  color: var(--primary);
  text-align: center;
  padding: var(--space-xs);
  cursor: pointer;
}

.kanban-more:hover {
  text-decoration: underline;
}

.kanban-connector {
  display: flex;
  align-items: center;
  padding-top: 40px; /* Align with cards, not header */
}

.connector-arrow {
  font-size: var(--text-xl);
  color: var(--text-disabled);
}

@media (max-width: 768px) {
  .kanban-board {
    flex-direction: column;
  }

  .kanban-column {
    min-width: 100%;
  }

  .kanban-connector {
    padding-top: 0;
    justify-content: center;
  }

  .connector-arrow {
    transform: rotate(90deg);
  }
}

/* ── Agent Cards Grid ────────────────────────────────────────── */
.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-lg);
}

.agent-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  transition: all var(--transition-normal);
}

.agent-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.agent-info {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.agent-icon {
  font-size: var(--text-4xl);
  line-height: 1;
}

.agent-name {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.3px;
}

.agent-worker {
  font-size: var(--text-xs);
  color: var(--text-disabled);
  font-family: var(--font-mono);
  margin-top: 2px;
  display: block;
}

/* ── Stage Info ──────────────────────────────────────────────── */
.agent-stage {
  display: inline-flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-xs) var(--space-md);
  background: var(--primary-light);
  border-radius: var(--radius-full);
  align-self: flex-start;
}

.stage-label {
  font-size: var(--text-xs);
  color: var(--primary);
  font-weight: 500;
}

.stage-value {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--primary-dark);
}

/* ── Progress ────────────────────────────────────────────────── */
.agent-progress {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.agent-progress .progress-bar {
  flex: 1;
}

.progress-text {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 40px;
  text-align: right;
}

/* ── Detail ──────────────────────────────────────────────────── */
.agent-detail {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--primary);
}

/* ── Alerts ──────────────────────────────────────────────────── */
.agent-alert {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
}

.alert-warning {
  background: var(--warning-light);
  color: #7c6c00;
}

.alert-danger {
  background: var(--danger-light);
  color: var(--danger);
}

.alert-message {
  flex: 1;
}

.retry-btn {
  flex-shrink: 0;
  padding: 2px 8px;
  font-size: var(--text-xs);
  color: var(--danger);
  border-color: var(--danger);
}

.retry-btn:hover {
  background: var(--danger);
  color: white;
}

/* ── Sub-workers ────────────────────────────────────────────── */
.sub-workers {
  border-top: 1px solid var(--divider);
  padding-top: var(--space-sm);
}

.sub-workers-header {
  margin-bottom: var(--space-xs);
}

.sub-workers-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  font-weight: 500;
}

.sub-workers-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.sub-worker-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-xs) var(--space-sm);
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  border-left: 2px solid var(--border-color);
}

.sub-worker-item.status-completed {
  border-left-color: var(--success);
}

.sub-worker-item.status-running {
  border-left-color: var(--primary);
}

.sub-worker-item.status-failed {
  border-left-color: var(--danger);
}

.sub-worker-name {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  min-width: 80px;
}

.sub-worker-progress {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.progress-bar-sm {
  height: 3px;
}

.sub-worker-pct {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  min-width: 32px;
  text-align: right;
}

/* ── Empty State ─────────────────────────────────────────────── */
.empty-state {
  padding: var(--space-4xl);
  text-align: center;
}

.empty-state-animation {
  position: relative;
  display: inline-block;
  margin-bottom: var(--space-lg);
}

.empty-state-icon {
  font-size: 64px;
  position: relative;
  z-index: 1;
}

.empty-state-pulse {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--primary-light);
  animation: pulse 2s infinite;
  z-index: 0;
}

.empty-state-title {
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-sm);
}

.empty-state-description {
  font-size: var(--text-md);
  color: var(--text-tertiary);
  margin-bottom: var(--space-xl);
}

.empty-state-action {
  display: flex;
  justify-content: center;
}

/* ── Pending Review Card ─────────────────────────────────────── */
.pending-review-card {
  border-left: 3px solid var(--warning);
}

.pending-review-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.view-all-link {
  font-size: var(--text-sm);
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
}

.view-all-link:hover {
  text-decoration: underline;
}

.pending-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.pending-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-lg);
  padding: var(--space-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  transition: background 0.2s;
}

.pending-item:hover {
  background: var(--bg-hover);
}

.pending-info {
  flex: 1;
  min-width: 0;
}

.pending-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-xs) 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pending-meta {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.meta-tag {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  background: var(--bg-card);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.pending-actions {
  display: flex;
  gap: var(--space-sm);
  align-items: center;
  flex-shrink: 0;
}

.reject-reason-input {
  width: 150px;
  padding: 4px 8px;
  font-size: var(--text-sm);
}

.btn-xs {
  padding: 4px 8px;
  font-size: var(--text-xs);
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .agents-grid {
    grid-template-columns: 1fr;
  }

  .timeline {
    justify-content: flex-start;
  }

  .pending-item {
    flex-direction: column;
    align-items: flex-start;
  }

  .pending-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
