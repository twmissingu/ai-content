<script setup lang="ts">
/**
 * PipelineStatusCards — timeline, budget, kanban board, and quality flywheel.
 * Extracted from PipelineView.vue to reduce its size.
 */
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import StatusBadge from './StatusBadge.vue'

const store = useDashboardStore()

// ── Current time (auto-refresh every minute) ──────────────────────────
const currentTime = ref(new Date())
let timeInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  timeInterval = setInterval(() => {
    currentTime.value = new Date()
  }, 60000)
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
    timeInterval = null
  }
})

const formattedTime = computed(() =>
  currentTime.value.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
)

// ── Timeline ───────────────────────────────────────────────────────────
const timelineItems = computed(() => {
  const schedule = store.config?.schedule
  if (!schedule) {
    return [
      { time: '09:00', label: 'Scout 选题', hour: 9, minute: 0 },
      { time: '09:30', label: '人工确认', hour: 9, minute: 30 },
      { time: '09:30', label: 'Writer 写作', hour: 9, minute: 30 },
      { time: '10:45', label: '审批', hour: 10, minute: 45 },
      { time: '11:00', label: '分发', hour: 11, minute: 0 },
    ]
  }
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

function getTimelineStatus(item: { hour: number; minute: number }): 'completed' | 'active' | 'pending' {
  const now = currentTime.value
  const itemMinutes = item.hour * 60 + item.minute
  const currentMinutes = now.getHours() * 60 + now.getMinutes()
  if (currentMinutes >= itemMinutes + 30) return 'completed'
  if (currentMinutes >= itemMinutes) return 'active'
  return 'pending'
}

// ── Kanban counts ──────────────────────────────────────────────────────
const kanbanCounts = computed(() => {
  const agentData = store.agents
  const scoutRunning = agentData.scout && agentData.scout.progress_pct < 100 && !agentData.scout.error
  const writerRunning = agentData.writer && agentData.writer.progress_pct < 100 && !agentData.writer.error
  return {
    discovering: scoutRunning ? 1 : 0,
    writing: writerRunning ? 1 : 0,
    pending: store.approvalQueue.length,
    published: 0,
  }
})

const agents = computed(() => store.agents as Record<string, any>)
</script>

<template>
  <!-- ── Timeline ──────────────────────────────────────────── -->
  <div class="card timeline-card">
    <div class="card-header">
      <h3 class="card-title">📅 今日时间线</h3>
      <span class="timeline-current-time" aria-live="polite">
        当前时间: {{ formattedTime }}
      </span>
    </div>
    <div class="timeline" role="list" aria-label="每日时间线">
      <template v-for="(item, index) in timelineItems" :key="item.time + item.label">
        <div class="timeline-item" :class="getTimelineStatus(item)" role="listitem">
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

  <!-- ── Budget ────────────────────────────────────────────── -->
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
      <div
        class="progress-bar"
        role="progressbar"
        :aria-valuenow="Math.min(store.budget.percentage || 0, 100)"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-label="`预算使用 ${store.budget.percentage?.toFixed(1) || 0}%`"
      >
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

  <!-- ── Content Pipeline Kanban ───────────────────────────── -->
  <div class="card pipeline-kanban-card">
    <div class="card-header">
      <h3 class="card-title">📋 内容流转</h3>
      <span class="kanban-hint">实时显示内容在管线中的位置</span>
    </div>
    <div class="kanban-board" role="region" aria-label="内容流转看板">
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
            role="button"
            tabindex="0"
            aria-label="前往审批页面"
            @click="$router.push('/approval')"
            @keydown.enter="$router.push('/approval')"
            @keydown.space.prevent="$router.push('/approval')"
          >
            <div class="kanban-card-title">{{ article.meta.topic || '未知选题' }}</div>
            <div class="kanban-card-meta">
              <span>📊 {{ article.meta.proofread_score || '-' }}分</span>
              <span>📝 {{ article.meta.word_count || 0 }}字</span>
            </div>
          </div>
          <div
            v-if="store.approvalQueue.length > 3"
            class="kanban-more"
            role="link"
            tabindex="0"
            aria-label="查看更多待审批文章"
            @click="$router.push('/approval')"
            @keydown.enter="$router.push('/approval')"
            @keydown.space.prevent="$router.push('/approval')"
          >
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

  <!-- ── Quality Flywheel ──────────────────────────────────── -->
  <div v-if="store.flywheelData?.recommended_thresholds" class="card flywheel-card">
    <div class="card-header">
      <h3 class="card-title">🎯 质量飞轮</h3>
      <span class="flywheel-badge">自动校准</span>
    </div>
    <p class="flywheel-message">{{ store.flywheelData.message }}</p>
    <div class="flywheel-thresholds">
      <div class="flywheel-threshold">
        <span class="flywheel-label">审校阈值</span>
        <span class="flywheel-value">{{ store.flywheelData.recommended_thresholds.proofread_threshold }}</span>
      </div>
      <div class="flywheel-threshold">
        <span class="flywheel-label">批评阈值</span>
        <span class="flywheel-value">{{ store.flywheelData.recommended_thresholds.critique_threshold }}</span>
      </div>
      <div class="flywheel-threshold">
        <span class="flywheel-label">标题阈值</span>
        <span class="flywheel-value">{{ store.flywheelData.recommended_thresholds.title_threshold }}</span>
      </div>
    </div>
    <div class="flywheel-meta">
      基于 {{ store.flywheelData.sample_size }} 条审批记录
      ({{ store.flywheelData.approved_scores?.length || 0 }} 通过 / {{ store.flywheelData.rejected_scores?.length || 0 }} 驳回)
    </div>
  </div>
</template>

<style scoped>
/* ── Timeline ──────────────────────────────────────────────── */
.timeline-card { overflow: hidden; }
.timeline-card .card-header { display: flex; justify-content: space-between; align-items: center; }
.timeline-current-time { font-size: var(--text-sm); color: var(--text-tertiary); font-weight: 500; }

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

.timeline-item.completed .timeline-time { color: var(--success); }
.timeline-item.active .timeline-time { color: var(--primary); font-weight: 700; }
.timeline-time { font-size: var(--text-sm); font-weight: 600; color: var(--text-primary); }

.timeline-dot {
  width: 24px; height: 24px; border-radius: 50%;
  background: var(--bg-card); border: 2px solid var(--border-color);
  display: flex; align-items: center; justify-content: center;
  transition: all var(--transition-fast);
}

.timeline-item.completed .timeline-dot {
  background: var(--success); border-color: var(--success); color: white;
}

.timeline-item.active .timeline-dot {
  background: var(--primary); border-color: var(--primary);
  box-shadow: 0 0 0 4px var(--primary-light); animation: pulse 2s infinite;
}

.dot-icon { font-size: 12px; font-weight: 700; }
.dot-pulse { width: 8px; height: 8px; background: white; border-radius: 50%; }
.timeline-label { font-size: var(--text-sm); color: var(--text-secondary); white-space: nowrap; }
.timeline-item.completed .timeline-label { color: var(--success); }
.timeline-item.active .timeline-label { color: var(--primary); font-weight: 600; }

.timeline-connector {
  flex: 1; height: 2px; background: var(--border-color);
  min-width: 20px; transition: background var(--transition-fast);
}
.timeline-connector.completed { background: var(--success); }

/* ── Budget ────────────────────────────────────────────────── */
.budget-card { background: linear-gradient(135deg, var(--bg-card) 0%, var(--primary-light) 100%); }
.budget-stats { display: flex; flex-direction: column; gap: var(--space-md); }
.budget-amount { font-size: var(--text-4xl); font-weight: 700; color: var(--text-primary); }
.budget-separator { color: var(--text-tertiary); margin: 0 var(--space-sm); }
.budget-limit { font-size: var(--text-xl); font-weight: 400; color: var(--text-tertiary); }
.budget-percentage { font-size: var(--text-sm); color: var(--text-secondary); }

/* ── Kanban ────────────────────────────────────────────────── */
.pipeline-kanban-card { overflow: hidden; }
.pipeline-kanban-card .card-header { display: flex; justify-content: space-between; align-items: center; }
.kanban-hint { font-size: var(--text-xs); color: var(--text-tertiary); }

.kanban-board {
  display: flex; align-items: flex-start; gap: var(--space-sm);
  overflow-x: auto; padding-bottom: var(--space-sm);
}

.kanban-column {
  flex: 1; min-width: 160px; background: var(--bg-hover);
  border-radius: var(--radius-lg); padding: var(--space-md);
}

.kanban-column-header {
  display: flex; align-items: center; gap: var(--space-sm);
  margin-bottom: var(--space-md); padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--divider);
}

.kanban-column-icon { font-size: var(--text-lg); }
.kanban-column-title { font-size: var(--text-sm); font-weight: 600; color: var(--text-primary); flex: 1; }

.kanban-column-count {
  font-size: var(--text-xs); font-weight: 600; background: var(--bg-card);
  color: var(--text-secondary); padding: 2px 8px; border-radius: var(--radius-full);
  min-width: 20px; text-align: center;
}
.kanban-column-count.has-items { background: var(--warning); color: white; }
.kanban-cards { display: flex; flex-direction: column; gap: var(--space-sm); }

.kanban-card {
  background: var(--bg-card); border-radius: var(--radius-md);
  padding: var(--space-sm) var(--space-md); border: 1px solid var(--border-light);
  cursor: pointer; transition: all var(--transition-fast);
}
.kanban-card:hover { box-shadow: var(--shadow-md); transform: translateY(-1px); }
.kanban-card:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.kanban-card.kanban-active { border-left: 3px solid var(--primary); background: var(--primary-light); }
.kanban-card.kanban-success { border-left: 3px solid var(--success); background: var(--success-light); }
.kanban-card-title { font-size: var(--text-sm); font-weight: 600; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kanban-card-detail, .kanban-card-meta { font-size: var(--text-xs); color: var(--text-tertiary); margin-top: 2px; display: flex; gap: var(--space-sm); }
.kanban-empty { font-size: var(--text-xs); color: var(--text-disabled); text-align: center; padding: var(--space-md); }
.kanban-more { font-size: var(--text-xs); color: var(--primary); text-align: center; padding: var(--space-xs); cursor: pointer; }
.kanban-more:hover { text-decoration: underline; }
.kanban-more:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; text-decoration: underline; }
.kanban-connector { display: flex; align-items: center; padding-top: 40px; }
.connector-arrow { font-size: var(--text-xl); color: var(--text-disabled); }

/* ── Flywheel ──────────────────────────────────────────────── */
.flywheel-card {
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--success-light) 100%);
  border-left: 3px solid var(--success);
}
.flywheel-card .card-header { display: flex; justify-content: space-between; align-items: center; }
.flywheel-badge { font-size: var(--text-xs); color: var(--success); background: var(--success-light); padding: 2px 8px; border-radius: var(--radius-full); font-weight: 600; }
.flywheel-message { font-size: var(--text-sm); color: var(--text-secondary); margin: 0 0 var(--space-md) 0; }
.flywheel-thresholds { display: flex; gap: var(--space-lg); margin-bottom: var(--space-md); }
.flywheel-threshold { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.flywheel-label { font-size: var(--text-xs); color: var(--text-tertiary); }
.flywheel-value { font-size: var(--text-2xl); font-weight: 700; color: var(--success); }
.flywheel-meta { font-size: var(--text-xs); color: var(--text-disabled); }

/* ── Responsive ────────────────────────────────────────────── */
@media (max-width: 768px) {
  .kanban-board { flex-direction: column; }
  .kanban-column { min-width: 100%; }
  .kanban-connector { padding-top: 0; justify-content: center; }
  .connector-arrow { transform: rotate(90deg); }
  .timeline { justify-content: flex-start; }
}
</style>
