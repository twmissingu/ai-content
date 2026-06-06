import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PipelineView from '../PipelineView.vue'
import { useDashboardStore } from '../../stores/dashboard'

// Mock the composables
vi.mock('../../composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
}))

vi.mock('../../composables/useKeyboardShortcut', () => ({
  useKeyboardShortcut: vi.fn(),
  isInputElement: vi.fn(() => false),
}))

describe('PipelineView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders the pipeline view', () => {
    const wrapper = mount(PipelineView)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays pipeline trigger panel', () => {
    const wrapper = mount(PipelineView)
    expect(wrapper.findComponent({ name: 'PipelineTriggerPanel' }).exists()).toBe(true)
  })

  it('displays pipeline status cards', () => {
    const wrapper = mount(PipelineView)
    expect(wrapper.findComponent({ name: 'PipelineStatusCards' }).exists()).toBe(true)
  })

  it('displays pipeline trace timeline', () => {
    const wrapper = mount(PipelineView)
    expect(wrapper.findComponent({ name: 'PipelineTraceTimeline' }).exists()).toBe(true)
  })

  it('computes pendingArticles correctly', async () => {
    const store = useDashboardStore()
    store.approvalQueue = [
      { id: '1', meta: {}, content_preview: '', source: 'filesystem' },
      { id: '2', meta: {}, content_preview: '', source: 'filesystem' },
      { id: '3', meta: {}, content_preview: '', source: 'filesystem' },
      { id: '4', meta: {}, content_preview: '', source: 'filesystem' },
    ]

    const wrapper = mount(PipelineView)
    const vm = wrapper.vm as any
    
    // Should only show first 3
    expect(vm.pendingArticles).toHaveLength(3)
  })

  it('quickApprove calls store.approve', async () => {
    const store = useDashboardStore()
    store.approve = vi.fn().mockResolvedValue({ status: 'ok' })
    store.fetchApprovalQueue = vi.fn().mockResolvedValue(undefined)

    const wrapper = mount(PipelineView)
    const vm = wrapper.vm as any

    await vm.quickApprove('test-id')
    
    expect(store.approve).toHaveBeenCalledWith('test-id')
    expect(store.fetchApprovalQueue).toHaveBeenCalled()
  })

  it('quickReject calls store.reject with reason', async () => {
    const store = useDashboardStore()
    store.reject = vi.fn().mockResolvedValue({ status: 'ok' })
    store.fetchApprovalQueue = vi.fn().mockResolvedValue(undefined)

    const wrapper = mount(PipelineView)
    const vm = wrapper.vm as any
    vm.quickRejectReason = '测试驳回原因'

    await vm.quickReject('test-id')
    
    expect(store.reject).toHaveBeenCalledWith('test-id', '测试驳回原因')
    expect(store.fetchApprovalQueue).toHaveBeenCalled()
  })

  it('quickReject does nothing without reason', async () => {
    const store = useDashboardStore()
    store.reject = vi.fn()

    const wrapper = mount(PipelineView)
    const vm = wrapper.vm as any
    vm.quickRejectReason = ''

    await vm.quickReject('test-id')
    
    expect(store.reject).not.toHaveBeenCalled()
  })

  it('getAgentIcon returns correct icon', () => {
    const wrapper = mount(PipelineView)
    const vm = wrapper.vm as any

    expect(vm.getAgentIcon('scout')).toBe('🔍')
    expect(vm.getAgentIcon('writer')).toBe('✍️')
    expect(vm.getAgentIcon('publisher')).toBe('📤')
    expect(vm.getAgentIcon('feedback')).toBe('📊')
    expect(vm.getAgentIcon('unknown')).toBe('⚙️')
  })

  it('getAgentLabel returns correct label', () => {
    const wrapper = mount(PipelineView)
    const vm = wrapper.vm as any

    expect(vm.getAgentLabel('scout')).toBe('选题侦察')
    expect(vm.getAgentLabel('writer')).toBe('内容写作')
    expect(vm.getAgentLabel('publisher')).toBe('平台分发')
    expect(vm.getAgentLabel('feedback')).toBe('数据回收')
    expect(vm.getAgentLabel('unknown')).toBe('unknown')
  })

  it('getProgressColor returns correct color', () => {
    const wrapper = mount(PipelineView)
    const vm = wrapper.vm as any

    expect(vm.getProgressColor(100)).toBe('success')
    expect(vm.getProgressColor(80)).toBe('primary')
    expect(vm.getProgressColor(50)).toBe('warning')
  })

  it('agentList computes from store.agents', async () => {
    const store = useDashboardStore()
    store.agents = {
      scout: { agent: 'scout', progress_pct: 100 },
      writer: { agent: 'writer', progress_pct: 50 },
    }

    const wrapper = mount(PipelineView)
    const vm = wrapper.vm as any

    expect(vm.agentList).toHaveLength(2)
    expect(vm.agentList[0].name).toBe('scout')
    expect(vm.agentList[1].name).toBe('writer')
  })
})
