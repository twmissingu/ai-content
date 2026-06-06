import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import TopicsView from '../TopicsView.vue'
import { useDashboardStore } from '../../stores/dashboard'

// Mock the composables
vi.mock('../../composables/useKeyboardShortcut', () => ({
  useKeyboardShortcut: vi.fn(),
  isInputElement: vi.fn(() => false),
}))

describe('TopicsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders the topics view', () => {
    const wrapper = mount(TopicsView)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays topic count', async () => {
    const store = useDashboardStore()
    store.topics = [
      { id: '1', title: 'Topic 1', source: 'weibo' },
      { id: '2', title: 'Topic 2', source: 'github' },
    ]

    const wrapper = mount(TopicsView)
    expect(wrapper.text()).toContain('2 个候选')
  })

  it('getScoreColor returns correct color', () => {
    const wrapper = mount(TopicsView)
    const vm = wrapper.vm as any

    expect(vm.getScoreColor(90)).toBe('success')
    expect(vm.getScoreColor(80)).toBe('primary')
    expect(vm.getScoreColor(60)).toBe('warning')
    expect(vm.getScoreColor(40)).toBe('neutral')
  })

  it('getScoreLabel returns correct label', () => {
    const wrapper = mount(TopicsView)
    const vm = wrapper.vm as any

    expect(vm.getScoreLabel(90)).toBe('强推')
    expect(vm.getScoreLabel(80)).toBe('候选')
    expect(vm.getScoreLabel(60)).toBe('待定')
    expect(vm.getScoreLabel(40)).toBe('较低')
  })

  it('getSourceIcon returns correct icon', () => {
    const wrapper = mount(TopicsView)
    const vm = wrapper.vm as any

    expect(vm.getSourceIcon('twitter')).toBe('🐦')
    expect(vm.getSourceIcon('github')).toBe('🐙')
    expect(vm.getSourceIcon('zhihu')).toBe('💡')
    expect(vm.getSourceIcon('weibo')).toBe('🔥')
    expect(vm.getSourceIcon('unknown')).toBe('📌')
  })

  it('truncateText truncates long text', () => {
    const wrapper = mount(TopicsView)
    const vm = wrapper.vm as any

    const longText = 'A'.repeat(200)
    expect(vm.truncateText(longText, 100)).toHaveLength(103) // 100 + '...'
    expect(vm.truncateText('Short text')).toBe('Short text')
    expect(vm.truncateText('')).toBe('')
  })

  it('paginatedTopics slices correctly', async () => {
    const store = useDashboardStore()
    store.topics = Array.from({ length: 25 }, (_, i) => ({
      id: `${i + 1}`,
      title: `Topic ${i + 1}`,
      source: 'weibo',
    }))

    const wrapper = mount(TopicsView)
    const vm = wrapper.vm as any

    // Page 1
    expect(vm.paginatedTopics).toHaveLength(10)
    expect(vm.paginatedTopics[0].id).toBe('1')
    
    // Page 2
    vm.currentPage = 2
    expect(vm.paginatedTopics[0].id).toBe('11')
    
    // Page 3 (partial)
    vm.currentPage = 3
    expect(vm.paginatedTopics).toHaveLength(5)
  })

  it('openReader sets reader state', () => {
    const wrapper = mount(TopicsView)
    const vm = wrapper.vm as any

    expect(vm.readerVisible).toBe(false)
    expect(vm.readerUrl).toBeNull()

    vm.openReader('https://example.com')
    expect(vm.readerVisible).toBe(true)
    expect(vm.readerUrl).toBe('https://example.com')
  })

  it('closeReader clears reader state', () => {
    const wrapper = mount(TopicsView)
    const vm = wrapper.vm as any

    vm.openReader('https://example.com')
    vm.closeReader()
    
    expect(vm.readerVisible).toBe(false)
  })

  it('displays reader panel when visible', async () => {
    const store = useDashboardStore()
    store.topics = [
      { id: '1', title: 'Topic 1', source: 'weibo', url: 'https://example.com' },
    ]

    const wrapper = mount(TopicsView)
    const vm = wrapper.vm as any

    vm.openReader('https://example.com')
    await wrapper.vm.$nextTick()
    
    expect(wrapper.findComponent({ name: 'ReaderPanel' }).exists()).toBe(true)
  })
})
