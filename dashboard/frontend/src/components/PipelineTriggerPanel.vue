<script setup lang="ts">
/**
 * PipelineTriggerPanel — manual trigger buttons + confirmation dialog.
 * Extracted from PipelineView.vue to reduce its size.
 */
import { ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { useToast } from '../composables/useToast'
import ConfirmDialog from './ConfirmDialog.vue'
import { API_BASE } from '../utils/api'

const store = useDashboardStore()
const toast = useToast()

const showTriggerDialog = ref(false)
const triggerTarget = ref<string>('')
const triggerLoading = ref(false)

function openTriggerDialog(agent: string) {
  triggerTarget.value = agent
  showTriggerDialog.value = true
}

async function confirmTrigger() {
  triggerLoading.value = true
  try {
    
    const res = await fetch(`${API_BASE}/api/pipeline/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent: triggerTarget.value }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    toast.success(`${triggerTarget.value === 'scout' ? 'Scout 选题' : 'Writer 写作'}已触发`)
    await store.fetchPipeline()
  } catch (e) {
    toast.error(`触发失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    triggerLoading.value = false
    showTriggerDialog.value = false
  }
}
</script>

<template>
  <div class="trigger-panel" role="group" aria-label="管线触发控制">
    <button
      class="btn btn-primary btn-sm"
      aria-label="执行 Scout 选题"
      @click="openTriggerDialog('scout')"
    >
      🔍 执行选题
    </button>
    <button
      class="btn btn-primary btn-sm"
      aria-label="执行 Writer 写作"
      @click="openTriggerDialog('writer')"
    >
      ✍️ 执行写作
    </button>

    <ConfirmDialog
      v-model:show="showTriggerDialog"
      title="手动触发"
      :message="`确定要立即执行${triggerTarget === 'scout' ? 'Scout 选题' : 'Writer 写作'}吗？`"
      confirmText="立即执行"
      :loading="triggerLoading"
      @confirm="confirmTrigger"
    />
  </div>
</template>

<style scoped>
.trigger-panel {
  display: flex;
  gap: var(--space-sm);
}
</style>
