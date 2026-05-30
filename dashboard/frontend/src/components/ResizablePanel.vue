<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  side: 'left' | 'right'
  minWidth?: number
  maxWidth?: number
  defaultWidth?: number
}>(), {
  minWidth: 200,
  maxWidth: 400,
  defaultWidth: 280,
})

const width = ref(props.defaultWidth)
const isResizing = ref(false)

function onMouseDown(e: MouseEvent) {
  e.preventDefault()
  isResizing.value = true
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onMouseMove(e: MouseEvent) {
  if (!isResizing.value) return
  if (props.side === 'left') {
    width.value = Math.min(props.maxWidth, Math.max(props.minWidth, e.clientX))
  } else {
    width.value = Math.min(props.maxWidth, Math.max(props.minWidth, window.innerWidth - e.clientX))
  }
}

function onMouseUp() {
  isResizing.value = false
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

onUnmounted(() => {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
})
</script>

<template>
  <div
    class="resizable-panel"
    :class="[`panel-${side}`, { resizing: isResizing }]"
    :style="{ width: width + 'px' }"
  >
    <slot />
    <div
      class="resize-handle"
      :class="`handle-${side}`"
      @mousedown="onMouseDown"
    />
  </div>
</template>

<style scoped>
.resizable-panel {
  position: relative;
  flex-shrink: 0;
  overflow: hidden;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.panel-left {
  border-right: none;
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}

.panel-right {
  border-left: none;
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
}

.resize-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 6px;
  cursor: col-resize;
  z-index: 10;
  transition: background var(--transition-fast);
}

.resize-handle:hover,
.resizing .resize-handle {
  background: var(--primary-light);
}

.handle-left {
  right: 0;
}

.handle-right {
  left: 0;
}
</style>
