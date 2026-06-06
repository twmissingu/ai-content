import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ApprovalView from '../ApprovalView.vue'
import { useDashboardStore } from '../../stores/dashboard'

// Mock the composables
vi.mock('../../composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
}))

vi.mock('../../composables/useKeyboardShortcut', () => ({
  useKeyboardShortcut: vi.fn(),
  isInputElement: vi.fn(() => false),
}))

describe('ApprovalView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders the approval view', () => {
    const wrapper = mount(ApprovalView)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays approval queue table', () => {
    const wrapper = mount(ApprovalView)
    expect(wrapper.findComponent({ name: 'ApprovalQueueTable' }).exists()).toBe(true)
  })

  it('displays pagination bar when queue is large', () => {
    const store = useDashboardStore()
    // pageSize is 10, so we need more than 10 items
    store.approvalQueue = Array.from({ length: 15 }, (_, i) => ({
      id: `${i + 1}`,
      meta: {},
      content_preview: '',
      source: 'filesystem',
    }))

    const wrapper = mount(ApprovalView)
    expect(wrapper.findComponent({ name: 'PaginationBar' }).exists()).toBe(true)
  })

  it('toggles batch mode', async () => {
    const wrapper = mount(ApprovalView)
    const vm = wrapper.vm as any

    expect(vm.isBatchMode).toBe(false)
    vm.toggleBatchMode()
    expect(vm.isBatchMode).toBe(true)
    vm.toggleBatchMode()
    expect(vm.isBatchMode).toBe(false)
  })

  it('clears selection when exiting batch mode', async () => {
    const wrapper = mount(ApprovalView)
    const vm = wrapper.vm as any

    vm.toggleBatchMode()
    vm.selectedIds = new Set(['1', '2', '3'])
    vm.toggleBatchMode()
    
    expect(vm.selectedIds.size).toBe(0)
  })

  it('toggleSelectAll selects all articles', async () => {
    const store = useDashboardStore()
    store.approvalQueue = [
      { id: '1', meta: {}, content_preview: '', source: 'filesystem' },
      { id: '2', meta: {}, content_preview: '', source: 'filesystem' },
      { id: '3', meta: {}, content_preview: '', source: 'filesystem' },
    ]

    const wrapper = mount(ApprovalView)
    const vm = wrapper.vm as any

    vm.toggleBatchMode()
    vm.toggleSelectAll()
    
    expect(vm.selectedIds.size).toBe(3)
    expect(vm.allSelected).toBe(true)
  })

  it('toggleSelectAll deselects when all selected', async () => {
    const store = useDashboardStore()
    store.approvalQueue = [
      { id: '1', meta: {}, content_preview: '', source: 'filesystem' },
      { id: '2', meta: {}, content_preview: '', source: 'filesystem' },
    ]

    const wrapper = mount(ApprovalView)
    const vm = wrapper.vm as any

    vm.toggleBatchMode()
    vm.toggleSelectAll()
    expect(vm.selectedIds.size).toBe(2)
    
    vm.toggleSelectAll()
    expect(vm.selectedIds.size).toBe(0)
  })

  it('handleToggleSelection adds and removes items', async () => {
    const wrapper = mount(ApprovalView)
    const vm = wrapper.vm as any

    vm.toggleBatchMode()
    vm.handleToggleSelection('1')
    expect(vm.selectedIds.has('1')).toBe(true)
    
    vm.handleToggleSelection('1')
    expect(vm.selectedIds.has('1')).toBe(false)
  })

  it('paginatedArticles slices correctly', async () => {
    const store = useDashboardStore()
    store.approvalQueue = Array.from({ length: 25 }, (_, i) => ({
      id: `${i + 1}`,
      meta: {},
      content_preview: '',
      source: 'filesystem',
    }))

    const wrapper = mount(ApprovalView)
    const vm = wrapper.vm as any

    // Page 1
    expect(vm.paginatedArticles).toHaveLength(10)
    expect(vm.paginatedArticles[0].id).toBe('1')
    
    // Page 2
    vm.currentPage = 2
    expect(vm.paginatedArticles[0].id).toBe('11')
    
    // Page 3 (partial)
    vm.currentPage = 3
    expect(vm.paginatedArticles).toHaveLength(5)
  })

  it('allSelected computes correctly', async () => {
    const store = useDashboardStore()
    store.approvalQueue = [
      { id: '1', meta: {}, content_preview: '', source: 'filesystem' },
      { id: '2', meta: {}, content_preview: '', source: 'filesystem' },
    ]

    const wrapper = mount(ApprovalView)
    const vm = wrapper.vm as any

    expect(vm.allSelected).toBe(false)
    
    vm.toggleBatchMode()
    vm.toggleSelectAll()
    expect(vm.allSelected).toBe(true)
  })

  it('selectedCount returns correct count', async () => {
    const wrapper = mount(ApprovalView)
    const vm = wrapper.vm as any

    vm.toggleBatchMode()
    expect(vm.selectedCount).toBe(0)
    
    vm.handleToggleSelection('1')
    vm.handleToggleSelection('2')
    expect(vm.selectedCount).toBe(2)
  })
})
