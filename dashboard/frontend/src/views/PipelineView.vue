<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import StatusBadge from '../components/StatusBadge.vue'

const store = useDashboardStore()

const agentList = computed(() => {
  const entries = Object.entries(store.agents)
  return entries.map(([name, data]) => ({
    name,
    ...data,
  }))
})

const stageNames: Record<string, string> = {
  scout: '选题侦察',
  writer: '内容写作',
  publisher: '平台分发',
  feedback: '数据回收',
}
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <h2 style="margin: 0; font-size: 20px;">管线状态</h2>
      <button @click="store.fetchPipeline()" style="padding: 6px 16px; background: #1a73e8; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">刷新</button>
    </div>

    <!-- Timeline -->
    <div style="background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);">
      <h3 style="margin: 0 0 16px 0; font-size: 15px; color: #333;">今日时间线</h3>
      <div style="display: flex; gap: 8px; align-items: center; font-size: 13px; color: #666;">
        <span style="background: #e8f0fe; padding: 4px 12px; border-radius: 6px;">09:00 Scout</span>
        <span>→</span>
        <span style="background: #e8f0fe; padding: 4px 12px; border-radius: 6px;">09:30 确认</span>
        <span>→</span>
        <span style="background: #e8f0fe; padding: 4px 12px; border-radius: 6px;">09:30-10:30 Writer</span>
        <span>→</span>
        <span style="background: #e8f0fe; padding: 4px 12px; border-radius: 6px;">10:45 审批</span>
        <span>→</span>
        <span style="background: #e8f0fe; padding: 4px 12px; border-radius: 6px;">11:00 分发</span>
      </div>
    </div>

    <!-- Agent cards -->
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px;">
      <div v-for="agent in agentList" :key="agent.name"
        style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h3 style="margin: 0; font-size: 15px;">
            {{ stageNames[agent.name.replace('writer-worker-', 'writer').replace('-wechat', '')] || agent.name }}
          </h3>
          <StatusBadge :status="agent.stage === 'completed' || agent.progress_pct >= 100 ? 'completed' : 'running'" />
        </div>
        <div v-if="agent.stage_name" style="font-size: 13px; color: #555; margin-bottom: 8px;">
          {{ agent.stage_name }}
        </div>
        <div style="height: 6px; background: #e0e0e0; border-radius: 3px; margin-bottom: 8px; overflow: hidden;">
          <div :style="{ width: (agent.progress_pct || 0) + '%', height: '100%', background: agent.progress_pct >= 100 ? '#1e7e34' : '#1a73e8', borderRadius: '3px', transition: 'width 0.5s' }"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #888;">
          <span>{{ agent.detail || '' }}</span>
          <span>{{ agent.progress_pct || 0 }}%</span>
        </div>
        <div v-if="agent.timeout" style="margin-top: 8px; font-size: 12px; color: #c5221f; background: #fce8e6; padding: 4px 8px; border-radius: 4px;">
          ⚠️ 超时
        </div>
        <div v-if="agent.error" style="margin-top: 8px; font-size: 12px; color: #c5221f;">
          Error: {{ agent.error }}
        </div>
      </div>
    </div>
  </div>
</template>
