<script setup lang="ts">
interface Props {
  type?: 'text' | 'title' | 'avatar' | 'card' | 'button'
  width?: string
  height?: string
  count?: number
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  count: 1,
})

const skeletonClass = `skeleton-${props.type}`
</script>

<template>
  <div class="skeleton-loader">
    <div 
      v-for="i in count" 
      :key="i"
      class="skeleton"
      :class="skeletonClass"
      :style="{ width: props.width, height: props.height }"
    ></div>
  </div>
</template>

<style scoped>
.skeleton-loader {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.skeleton-text {
  height: 16px;
  width: 100%;
}

.skeleton-title {
  height: 24px;
  width: 60%;
}

.skeleton-avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
}

.skeleton-card {
  height: 120px;
  width: 100%;
}

.skeleton-button {
  height: 36px;
  width: 100px;
  border-radius: var(--radius-md);
}
</style>
