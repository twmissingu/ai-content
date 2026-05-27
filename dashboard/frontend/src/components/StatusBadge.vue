<script setup lang="ts">
interface Props {
  status: string
  size?: 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
})

const statusConfig: Record<string, { label: string, icon: string, class: string }> = {
  completed: { label: '完成', icon: '✅', class: 'success' },
  success: { label: '成功', icon: '✅', class: 'success' },
  running: { label: '运行中', icon: '⏳', class: 'primary' },
  in_progress: { label: '进行中', icon: '⏳', class: 'primary' },
  pending: { label: '待处理', icon: '⏸️', class: 'warning' },
  failed: { label: '失败', icon: '❌', class: 'danger' },
  error: { label: '错误', icon: '❌', class: 'danger' },
  idle: { label: '空闲', icon: '💤', class: 'neutral' },
  skipped: { label: '跳过', icon: '⏭️', class: 'neutral' },
}

const config = statusConfig[props.status] || { label: props.status, icon: '❓', class: 'neutral' }
</script>

<template>
  <span 
    class="status-badge"
    :class="[config.class, size]"
    :title="config.label"
  >
    <span class="badge-icon">{{ config.icon }}</span>
    <span class="badge-label">{{ config.label }}</span>
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  font-weight: 500;
  border-radius: var(--radius-full);
  white-space: nowrap;
  transition: all var(--transition-fast);
}

/* ── Sizes ───────────────────────────────────────────────────── */
.status-badge.sm {
  padding: 2px 8px;
  font-size: var(--text-xs);
}

.status-badge.md {
  padding: 4px 12px;
  font-size: var(--text-sm);
}

.status-badge.lg {
  padding: 6px 16px;
  font-size: var(--text-md);
}

.badge-icon {
  line-height: 1;
}

/* ── Variants ────────────────────────────────────────────────── */
.status-badge.success {
  background: var(--success-light);
  color: var(--success);
}

.status-badge.primary {
  background: var(--primary-light);
  color: var(--primary);
}

.status-badge.warning {
  background: var(--warning-light);
  color: var(--warning-dark);
}

.status-badge.danger {
  background: var(--danger-light);
  color: var(--danger);
}

.status-badge.neutral {
  background: var(--bg-hover);
  color: var(--text-secondary);
}

/* ── Hover Effects ───────────────────────────────────────────── */
.status-badge.success:hover {
  background: var(--success-hover-light);
}

.status-badge.primary:hover {
  background: var(--primary-hover-light);
}

.status-badge.warning:hover {
  background: var(--warning-hover-light);
}

.status-badge.danger:hover {
  background: var(--danger-hover-light);
}

.status-badge.neutral:hover {
  background: var(--bg-active);
}
</style>
