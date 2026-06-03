<script setup lang="ts">
/**
 * PipelineTraceTimeline — execution history sessions list with expandable trace details.
 * Extracted from PipelineView.vue to reduce its size.
 * Each session expands to show TraceTimeline for detailed stage breakdown.
 */
import { ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { useToast } from '../composables/useToast'
import StatusBadge from './StatusBadge.vue'
import TraceTimeline from './TraceTimeline.vue'

const store = useDashboardStore()
const toast = useToast()

const expandedSessionId = ref<number | null>(null)

function toggleSession(sessionId: number) {
  if (expandedSessionId.value === sessionId) {
    expandedSessionId.value = null
    store.clearActiveTraceSummary()
  } else {
    expandedSessionId.value = sessionId
    store.fetchTraceSummary(sessionId)
  }
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const m = Math.floor(ms / 60000)
  const s = Math.floor((ms % 60000) / 1000)
  return `${m}m${s}s`
}

async function handleRerun(stage: number) {
  try {
    await store.rerunFromStage(stage)
  } catch (e) {
    toast.error(`重跑失败: ${e instanceof Error ? e.message : '未知错误'}`)
  }
}

function refresh() {
  store.fetchTraceSessions()
}
</script>

<template>
  <div v-if="store.traceSessions.length > 0" class="card execution-history-card">
    <div class="card-header">
      <h3 class="card-title">📊 执行历史</h3>
      <button
        class="btn btn-ghost btn-xs"
        aria-label="刷新执行历史"
        @click="refresh"
      >
        🔄 刷新
      </button>
    </div>
    <div class="execution-list" role="list" aria-label="管线执行历史">
      <div
        v-for="session in store.traceSessions.slice(0, 10)"
        :key="session.id"
        class="execution-item"
        :class="{ expanded: expandedSessionId === session.id }"
        role="button"
        tabindex="0"
        :aria-expanded="expandedSessionId === session.id"
        :aria-label="`执行会话: ${session.topic || '未知选题'} — ${session.date}`"
        @click="toggleSession(session.id)"
        @keydown.enter="toggleSession(session.id)"
        @keydown.space.prevent="toggleSession(session.id)"
      >
        <div class="execution-row">
          <div class="execution-info">
            <span class="execution-topic">{{ session.topic || '未知选题' }}</span>
            <span class="execution-meta">
              {{ session.date }} {{ session.period === 'am' ? '上午' : '下午' }}
            </span>
          </div>
          <div class="execution-stats">
            <span class="execution-stages">{{ session.stage_count }} 阶段</span>
            <span class="execution-duration">{{ formatDuration(session.total_duration_ms) }}</span>
            <span v-if="session.failed_stages.length > 0" class="execution-failed">
              {{ session.failed_stages.length }} 失败
            </span>
            <StatusBadge :status="session.status" />
          </div>
          <span class="execution-expand">
            {{ expandedSessionId === session.id ? '▼' : '▶' }}
          </span>
        </div>

        <!-- Expanded trace detail -->
        <div v-if="expandedSessionId === session.id" class="execution-detail" @click.stop>
          <TraceTimeline
            :summary="store.activeTraceSummary"
            :loading="store.isLoading('traceSummary')"
            :show-rerun="true"
            @rerun="handleRerun"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.execution-history-card { overflow: hidden; }
.execution-history-card .card-header { display: flex; justify-content: space-between; align-items: center; }

.execution-list { display: flex; flex-direction: column; gap: 0; }

.execution-item {
  border-bottom: 1px solid var(--divider);
  cursor: pointer;
  transition: background var(--transition-fast);
}
.execution-item:last-child { border-bottom: none; }
.execution-item:hover { background: var(--bg-hover); }
.execution-item.expanded { background: var(--bg-hover); }

.execution-row {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md) var(--space-lg);
}

.execution-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.execution-topic {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.execution-meta {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.execution-stats {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-shrink: 0;
}

.execution-stages,
.execution-duration {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.execution-failed {
  font-size: var(--text-xs);
  color: var(--danger);
  font-weight: 600;
}

.execution-expand {
  font-size: var(--text-xs);
  color: var(--text-disabled);
  flex-shrink: 0;
  width: 16px;
  text-align: center;
}

.execution-detail {
  padding: 0 var(--space-lg) var(--space-lg) calc(var(--space-lg) + 44px);
  border-top: 1px solid var(--divider);
}
</style>
