<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  total: number
  pageSize?: number
  currentPage: number
}

const props = withDefaults(defineProps<Props>(), {
  pageSize: 20,
})

const emit = defineEmits<{
  'update:currentPage': [page: number]
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const visiblePages = computed(() => {
  const pages: number[] = []
  const total = totalPages.value
  const current = props.currentPage

  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i)
  } else {
    pages.push(1)
    if (current > 3) pages.push(-1) // ellipsis
    const start = Math.max(2, current - 1)
    const end = Math.min(total - 1, current + 1)
    for (let i = start; i <= end; i++) pages.push(i)
    if (current < total - 2) pages.push(-1) // ellipsis
    pages.push(total)
  }
  return pages
})

function goTo(page: number) {
  if (page >= 1 && page <= totalPages.value) {
    emit('update:currentPage', page)
  }
}
</script>

<template>
  <nav v-if="totalPages > 1" class="pagination" aria-label="分页导航">
    <button
      class="page-btn"
      :disabled="currentPage <= 1"
      @click="goTo(currentPage - 1)"
      aria-label="上一页"
    >
      ‹
    </button>

    <template v-for="(page, i) in visiblePages" :key="i">
      <span v-if="page === -1" class="page-ellipsis">…</span>
      <button
        v-else
        class="page-btn"
        :class="{ active: page === currentPage }"
        @click="goTo(page)"
        :aria-current="page === currentPage ? 'page' : undefined"
      >
        {{ page }}
      </button>
    </template>

    <button
      class="page-btn"
      :disabled="currentPage >= totalPages"
      @click="goTo(currentPage + 1)"
      aria-label="下一页"
    >
      ›
    </button>

    <span class="page-info">{{ total }} 条</span>
  </nav>
</template>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  justify-content: center;
  padding: var(--space-md) 0;
}

.page-btn {
  min-width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.page-btn:hover:not(:disabled):not(.active) {
  background: var(--bg-hover);
  border-color: var(--primary);
  color: var(--primary);
}

.page-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  font-weight: 600;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-ellipsis {
  color: var(--text-tertiary);
  padding: 0 2px;
}

.page-info {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-left: var(--space-sm);
}

@media (max-width: 768px) {
  .page-btn {
    min-width: 32px;
    height: 32px;
    font-size: var(--text-xs);
  }

  .page-info {
    display: none;
  }
}
</style>
