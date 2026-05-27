<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import StatusBadge from '../components/StatusBadge.vue'

const store = useDashboardStore()

const agentList = computed(() => {
  const entries = Object.entries(store.agents)
  return entries.map(([name, data]) => ({
    name,
    ...data,
  }))
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

// Current time with auto-refresh
const currentTime = ref(new Date())
let timeInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  timeInterval = setInterval(() => {
    currentTime.value = new Date()
  }, 60000) // Update every minute
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

// Timeline items with status
const timelineItems = [
  { time: '09:00', label: 'Scout 选题', hour: 9, minute: 0 },
  { time: '09:30', label: '人工确认', hour: 9, minute: 30 },
  { time: '09:30', label: 'Writer 写作', hour: 9, minute: 30 },
  { time: '10:45', label: '审批', hour: 10, minute: 45 },
  { time: '11:00', label: '分发', hour: 11, minute: 0 },
]

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
      <button class="btn btn-ghost btn-sm" @click="store.fetchPipeline()">
        <span>🔄</span> 刷新
      </button>
    </div>

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

    <!-- Agent Cards -->
    <div class="agents-grid">
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

        <!-- Detail -->
        <div v-if="agent.detail" class="agent-detail">
          {{ agent.detail }}
        </div>

        <!-- Alerts -->
        <div v-if="agent.timeout" class="agent-alert alert-warning">
          ⚠️ 运行超时
        </div>
        <div v-if="agent.error" class="agent-alert alert-danger">
          ❌ {{ agent.error }}
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="agentList.length === 0" class="card empty-state">
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

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .agents-grid {
    grid-template-columns: 1fr;
  }
  
  .timeline {
    justify-content: flex-start;
  }
}
</style>
