<script setup lang="ts">
import { computed } from 'vue'
import type { TraceSummary } from '../stores/dashboard'

const props = defineProps<{
  summary: TraceSummary | null
  loading?: boolean
  showRerun?: boolean
}>()

const emit = defineEmits<{
  rerun: [stage: number]
}>()

const stageMap: Record<string, number> = {
  fetch_source: 1,
  draft: 2,
  proofread: 3,
  critique: 4,
  format: 5,
  titles: 6,
  illustrate: 7,
}

const stages = computed(() => props.summary?.stages ?? [])
const totalTokens = computed(() => props.summary?.total_tokens ?? 0)
const totalDuration = computed(() => props.summary?.total_duration_ms ?? 0)

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const m = Math.floor(ms / 60000)
  const s = Math.floor((ms % 60000) / 1000)
  return `${m}m${s}s`
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

function statusIcon(status: string): string {
  switch (status) {
    case 'completed': return '✓'
    case 'failed': return '✗'
    case 'running': return '●'
    case 'skipped': return '⊘'
    default: return '?'
  }
}

function statusClass(status: string): string {
  switch (status) {
    case 'completed': return 'trace-completed'
    case 'failed': return 'trace-failed'
    case 'running': return 'trace-running'
    case 'skipped': return 'trace-skipped'
    default: return ''
  }
}

function agentIcon(agent: string): string {
  if (agent === 'scout') return '🔍'
  if (agent === 'writer') return '✍️'
  if (agent === 'publisher') return '📤'
  return '⚙️'
}

const maxWidthPx = 120
function durationBarWidth(ms: number | null): number {
  if (!ms || !totalDuration.value) return 0
  return Math.min((ms / totalDuration.value) * maxWidthPx, maxWidthPx)
}
</script>

<template>
  <div class="trace-timeline">
    <div v-if="loading" class="trace-loading">
      <div class="trace-skeleton" v-for="i in 3" :key="i"></div>
    </div>

    <div v-else-if="stages.length === 0" class="trace-empty">
      暂无执行记录
    </div>

    <template v-else>
      <!-- Summary bar -->
      <div class="trace-summary-bar">
        <span class="trace-stat">
          <span class="trace-stat-label">阶段</span>
          <span class="trace-stat-value">{{ stages.length }}</span>
        </span>
        <span class="trace-stat">
          <span class="trace-stat-label">耗时</span>
          <span class="trace-stat-value">{{ formatDuration(totalDuration) }}</span>
        </span>
        <span class="trace-stat">
          <span class="trace-stat-label">Token</span>
          <span class="trace-stat-value">{{ formatTokens(totalTokens) }}</span>
        </span>
        <span v-if="summary?.failed_stages?.length" class="trace-stat trace-stat-error">
          <span class="trace-stat-label">失败</span>
          <span class="trace-stat-value">{{ summary.failed_stages.length }}</span>
        </span>
      </div>

      <!-- Stage list -->
      <div class="trace-stages">
        <div
          v-for="(stage, i) in stages"
          :key="stage.id"
          class="trace-stage"
          :class="statusClass(stage.status)"
        >
          <!-- Connector line -->
          <div class="trace-connector">
            <div v-if="i > 0" class="trace-line"></div>
            <div class="trace-node" :class="statusClass(stage.status)">
              {{ statusIcon(stage.status) }}
            </div>
          </div>

          <!-- Stage content -->
          <div class="trace-stage-content">
            <div class="trace-stage-header">
              <span class="trace-agent-icon">{{ agentIcon(stage.agent) }}</span>
              <span class="trace-stage-name">{{ stage.stage_name || stage.stage }}</span>
              <span class="trace-agent-tag">{{ stage.agent }}</span>
              <span class="trace-duration">{{ formatDuration(stage.duration_ms) }}</span>
            </div>

            <!-- Duration bar -->
            <div class="trace-duration-bar-wrap">
              <div
                class="trace-duration-bar"
                :class="statusClass(stage.status)"
                :style="{ width: durationBarWidth(stage.duration_ms) + 'px' }"
              ></div>
            </div>

            <!-- Output/error -->
            <div v-if="stage.output_summary" class="trace-output">
              {{ stage.output_summary }}
            </div>
            <div v-if="stage.error_message" class="trace-error">
              {{ stage.error_message }}
            </div>

            <!-- Tokens -->
            <div v-if="stage.tokens_used" class="trace-tokens">
              {{ formatTokens(stage.tokens_used) }} tokens
            </div>

            <!-- Re-run button -->
            <button
              v-if="showRerun && stageMap[stage.stage]"
              class="trace-rerun-btn"
              @click.stop="emit('rerun', stageMap[stage.stage])"
              title="从此阶段重新执行"
            >
              ↻ 重跑
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.trace-timeline {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.trace-loading {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.trace-skeleton {
  height: 48px;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  animation: pulse 1.5s infinite;
}

.trace-empty {
  text-align: center;
  padding: var(--space-xl);
  color: var(--text-disabled);
  font-size: var(--text-sm);
}

/* Summary bar */
.trace-summary-bar {
  display: flex;
  gap: var(--space-lg);
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-hover);
  border-radius: var(--radius-md);
}

.trace-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.trace-stat-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.trace-stat-value {
  font-size: var(--text-md);
  font-weight: 700;
  color: var(--text-primary);
}

.trace-stat-error .trace-stat-value {
  color: var(--danger);
}

/* Stages */
.trace-stages {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.trace-stage {
  display: flex;
  gap: var(--space-md);
  padding: var(--space-xs) 0;
}

/* Connector */
.trace-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 28px;
  flex-shrink: 0;
}

.trace-line {
  width: 2px;
  height: 12px;
  background: var(--border-color);
}

.trace-node {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  border: 2px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-tertiary);
}

.trace-node.trace-completed {
  background: var(--success);
  border-color: var(--success);
  color: white;
}

.trace-node.trace-failed {
  background: var(--danger);
  border-color: var(--danger);
  color: white;
}

.trace-node.trace-running {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  animation: pulse 2s infinite;
}

.trace-node.trace-skipped {
  background: var(--bg-hover);
  border-color: var(--text-disabled);
  color: var(--text-disabled);
}

/* Content */
.trace-stage-content {
  flex: 1;
  min-width: 0;
  padding-bottom: var(--space-sm);
}

.trace-stage-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.trace-agent-icon {
  font-size: var(--text-sm);
}

.trace-stage-name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.trace-agent-tag {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  background: var(--bg-hover);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
}

.trace-duration {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  font-weight: 600;
  margin-left: auto;
}

/* Duration bar */
.trace-duration-bar-wrap {
  margin-top: 4px;
  height: 4px;
  background: var(--bg-hover);
  border-radius: 2px;
  overflow: hidden;
}

.trace-duration-bar {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.trace-duration-bar.trace-completed {
  background: var(--success);
}

.trace-duration-bar.trace-failed {
  background: var(--danger);
}

.trace-duration-bar.trace-running {
  background: var(--primary);
  animation: pulse 1.5s infinite;
}

/* Output/error */
.trace-output {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin-top: 4px;
  padding: var(--space-xs) var(--space-sm);
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-error {
  font-size: var(--text-xs);
  color: var(--danger);
  margin-top: 4px;
  padding: var(--space-xs) var(--space-sm);
  background: var(--danger-light);
  border-radius: var(--radius-sm);
}

.trace-tokens {
  font-size: var(--text-xs);
  color: var(--text-disabled);
  margin-top: 2px;
  font-family: var(--font-mono);
}

.trace-rerun-btn {
  margin-top: 4px;
  padding: 2px 8px;
  font-size: var(--text-xs);
  color: var(--primary);
  background: var(--primary-light);
  border: 1px solid var(--primary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  align-self: flex-start;
}

.trace-rerun-btn:hover {
  background: var(--primary);
  color: white;
}
</style>
