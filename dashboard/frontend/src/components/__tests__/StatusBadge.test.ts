import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusBadge from '../StatusBadge.vue'

describe('StatusBadge', () => {
  it('renders completed status', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'completed' } })
    expect(wrapper.text()).toContain('完成')
    expect(wrapper.find('.badge-icon').text()).toBe('✅')
    expect(wrapper.classes()).toContain('success')
  })

  it('renders running status', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'running' } })
    expect(wrapper.text()).toContain('运行中')
    expect(wrapper.classes()).toContain('primary')
  })

  it('renders failed status', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'failed' } })
    expect(wrapper.text()).toContain('失败')
    expect(wrapper.classes()).toContain('danger')
  })

  it('renders pending status', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'pending' } })
    expect(wrapper.text()).toContain('待处理')
    expect(wrapper.classes()).toContain('warning')
  })

  it('renders unknown status with fallback', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'custom' } })
    expect(wrapper.text()).toContain('custom')
    expect(wrapper.find('.badge-icon').text()).toBe('❓')
    expect(wrapper.classes()).toContain('neutral')
  })

  it('applies size class', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'idle', size: 'lg' } })
    expect(wrapper.classes()).toContain('lg')
  })

  it('defaults to md size', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'idle' } })
    expect(wrapper.classes()).toContain('md')
  })

  it('renders all known statuses', () => {
    const statuses = ['completed', 'success', 'running', 'in_progress', 'pending', 'failed', 'error', 'idle', 'skipped']
    for (const status of statuses) {
      const wrapper = mount(StatusBadge, { props: { status } })
      expect(wrapper.find('.badge-label').text()).toBeTruthy()
    }
  })
})
