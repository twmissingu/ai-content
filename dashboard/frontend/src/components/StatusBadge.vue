<script setup lang="ts">
defineProps<{ status: string }>()
</script>

<template>
  <span
    :style="{
      display: 'inline-block',
      padding: '2px 10px',
      borderRadius: '12px',
      fontSize: '12px',
      fontWeight: 500,
      background: status === 'completed' ? '#e6f4ea' : status === 'running' || status === 'in_progress' ? '#e8f0fe' : status === 'failed' || status === 'error' ? '#fce8e6' : '#f5f5f5',
      color: status === 'completed' ? '#1e7e34' : status === 'running' || status === 'in_progress' ? '#1a73e8' : status === 'failed' || status === 'error' ? '#c5221f' : '#666',
    }"
  >
    {{ status }}
  </span>
</template>
