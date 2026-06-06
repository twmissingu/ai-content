import { onMounted, onUnmounted } from 'vue'

/**
 * Returns true if the event target is an input-like element where
 * global keyboard shortcuts should be suppressed.
 */
export function isInputElement(el: EventTarget | null): boolean {
  if (!el || !(el instanceof HTMLElement)) return false
  const tag = el.tagName.toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable
}

/**
 * Registers a global keydown listener that automatically skips input elements
 * and cleans up on component unmount.
 *
 * @param handler - The keydown callback (view-specific logic lives here).
 *                  The handler receives the raw KeyboardEvent and should
 *                  already guard against input elements via `isInputElement`.
 */
export function useKeyboardShortcut(handler: (e: KeyboardEvent) => void): void {
  onMounted(() => {
    document.addEventListener('keydown', handler)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handler)
  })
}
