<script setup lang="ts">
import { ref, watch, nextTick, onUnmounted } from 'vue'

interface Props {
  show: boolean
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  confirmVariant?: 'primary' | 'danger' | 'success'
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '确认操作',
  message: '确定要执行此操作吗？',
  confirmText: '确认',
  cancelText: '取消',
  confirmVariant: 'primary',
  loading: false,
})

const emit = defineEmits<{
  confirm: []
  cancel: []
  'update:show': [value: boolean]
}>()

let previouslyFocused: HTMLElement | null = null
const overlayEl = ref<HTMLElement | null>(null)

function getFocusableElements(): HTMLElement[] {
  if (!overlayEl.value) return []
  const container = overlayEl.value.querySelector('.modal-container')
  if (!container) return []
  return Array.from(container.querySelectorAll<HTMLElement>(
    'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'
  ))
}

function trapFocus(e: KeyboardEvent) {
  if (e.key !== 'Tab') return
  const focusable = getFocusableElements()
  if (focusable.length === 0) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}

function onConfirm() {
  emit('confirm')
}

function onCancel() {
  emit('cancel')
  emit('update:show', false)
}

function onOverlayClick(e: MouseEvent) {
  if (e.target === e.currentTarget) {
    onCancel()
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    onCancel()
  }
  trapFocus(e)
}

watch(() => props.show, async (showing) => {
  if (showing) {
    previouslyFocused = document.activeElement as HTMLElement
    await nextTick()
    overlayEl.value?.focus()
    const focusable = getFocusableElements()
    if (focusable.length > 0) focusable[0].focus()
  } else {
    previouslyFocused?.focus()
    previouslyFocused = null
  }
})

onUnmounted(() => {
  previouslyFocused = null
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="modal-overlay"
        @click="onOverlayClick"
        @keydown="onKeydown"
        tabindex="-1"
        ref="overlayEl"
      >
        <div class="modal-container" role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title">
          <!-- Header -->
          <div class="modal-header">
            <h3 class="modal-title" id="confirm-dialog-title">{{ title }}</h3>
            <button class="modal-close" @click="onCancel" aria-label="关闭">✕</button>
          </div>

          <!-- Body -->
          <div class="modal-body">
            <slot>
              <p class="modal-message">{{ message }}</p>
            </slot>
          </div>

          <!-- Footer -->
          <div class="modal-footer">
            <button
              class="btn btn-ghost"
              @click="onCancel"
              :disabled="loading"
            >
              {{ cancelText }}
            </button>
            <button
              class="btn"
              :class="`btn-${confirmVariant}`"
              @click="onConfirm"
              :disabled="loading"
            >
              <span v-if="loading" class="loading-spinner-sm"></span>
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: var(--space-lg);
  backdrop-filter: blur(4px);
}

.modal-container {
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  max-width: 480px;
  width: 100%;
  max-height: 90vh;
  overflow: auto;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-xl) var(--space-xl) var(--space-lg);
}

.modal-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: var(--text-xl);
  padding: var(--space-xs);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.modal-close:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.modal-body {
  padding: 0 var(--space-xl) var(--space-xl);
}

.modal-message {
  color: var(--text-secondary);
  font-size: var(--text-md);
  line-height: 1.6;
  margin: 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-md);
  padding: var(--space-lg) var(--space-xl);
  border-top: 1px solid var(--border-light);
}

.loading-spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
  margin-right: var(--space-xs);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Transitions */
.modal-enter-active {
  transition: opacity 0.2s ease-out;
}

.modal-leave-active {
  transition: opacity 0.15s ease-in;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container {
  animation: modal-slide-up 0.2s ease-out;
}

.modal-leave-active .modal-container {
  animation: modal-slide-down 0.15s ease-in;
}

@keyframes modal-slide-up {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

@keyframes modal-slide-down {
  from {
    transform: translateY(0);
    opacity: 1;
  }
  to {
    transform: translateY(20px);
    opacity: 0;
  }
}

/* Mobile */
@media (max-width: 768px) {
  .modal-overlay {
    padding: var(--space-md);
    align-items: flex-end;
  }

  .modal-container {
    max-width: 100%;
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  }

  .modal-enter-active .modal-container {
    animation: modal-slide-up-mobile 0.3s ease-out;
  }

  @keyframes modal-slide-up-mobile {
    from {
      transform: translateY(100%);
    }
    to {
      transform: translateY(0);
    }
  }
}
</style>
