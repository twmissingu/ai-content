<script setup lang="ts">
import { ref, onUnmounted } from 'vue'

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
  document.addEventListener('touchmove', onTouchMove, { passive: false })
  document.addEventListener('touchend', onTouchEnd)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onMouseMove(e: MouseEvent) {
  if (!isResizing.value) return
  updateWidth(e.clientX)
}

function onMouseUp() {
  isResizing.value = false
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
  document.removeEventListener('touchmove', onTouchMove)
  document.removeEventListener('touchend', onTouchEnd)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

function onTouchMove(e: TouchEvent) {
  e.preventDefault()
  if (!isResizing.value || !e.touches[0]) return
  updateWidth(e.touches[0].clientX)
}

function onTouchEnd() {
  onMouseUp()
}

function onKeydown(e: KeyboardEvent) {
  const step = 10
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    width.value = Math.max(props.minWidth, width.value - step)
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    width.value = Math.min(props.maxWidth, width.value + step)
  }
}

function updateWidth(clientX: number) {
  if (props.side === 'left') {
    width.value = Math.min(props.maxWidth, Math.max(props.minWidth, clientX))
  } else {
    width.value = Math.min(props.maxWidth, Math.max(props.minWidth, window.innerWidth - clientX))
  }
}

onUnmounted(() => {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
  document.removeEventListener('touchmove', onTouchMove)
  document.removeEventListener('touchend', onTouchEnd)
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
      role="separator"
      aria-orientation="vertical"
      :aria-label="`${side === 'left' ? '左' : '右'}侧面板，拖拽调整宽度`"
      tabindex="0"
      @mousedown="onMouseDown"
      @keydown="onKeydown"
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
