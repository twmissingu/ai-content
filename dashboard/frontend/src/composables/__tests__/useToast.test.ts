import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useToast } from '../useToast'

describe('useToast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Clear shared toasts state between tests
    const { toasts } = useToast()
    toasts.value = []
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('adds a toast with success type', () => {
    const { toasts, success } = useToast()
    success('操作成功')
    expect(toasts.value).toHaveLength(1)
    expect(toasts.value[0].type).toBe('success')
    expect(toasts.value[0].message).toBe('操作成功')
  })

  it('adds a toast with error type', () => {
    const { toasts, error } = useToast()
    error('出错了')
    expect(toasts.value).toHaveLength(1)
    expect(toasts.value[0].type).toBe('error')
  })

  it('adds a toast with info type', () => {
    const { toasts, info } = useToast()
    info('提示信息')
    expect(toasts.value[0].type).toBe('info')
  })

  it('adds a toast with warning type', () => {
    const { toasts, warning } = useToast()
    warning('警告')
    expect(toasts.value[0].type).toBe('warning')
  })

  it('removes toast by id', () => {
    const { toasts, addToast, removeToast } = useToast()
    addToast('info', 'msg1')
    addToast('info', 'msg2')
    expect(toasts.value).toHaveLength(2)
    removeToast(toasts.value[0].id)
    expect(toasts.value).toHaveLength(1)
    expect(toasts.value[0].message).toBe('msg2')
  })

  it('auto-removes toast after duration', () => {
    const { toasts, success } = useToast()
    success('temporary', 1000)
    expect(toasts.value).toHaveLength(1)
    vi.advanceTimersByTime(1000)
    expect(toasts.value).toHaveLength(0)
  })

  it('caps at 5 toasts', () => {
    const { toasts, addToast } = useToast()
    for (let i = 0; i < 7; i++) {
      addToast('info', `msg${i}`)
    }
    expect(toasts.value).toHaveLength(5)
    expect(toasts.value[0].message).toBe('msg2') // first two were shifted
  })

  it('error has default 5000ms duration', () => {
    const { toasts, error } = useToast()
    error('fail')
    vi.advanceTimersByTime(4999)
    expect(toasts.value).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(toasts.value).toHaveLength(0)
  })

  it('warning has default 4000ms duration', () => {
    const { toasts, warning } = useToast()
    warning('warn')
    vi.advanceTimersByTime(3999)
    expect(toasts.value).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(toasts.value).toHaveLength(0)
  })
})
