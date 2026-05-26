<script setup lang="ts">
import { useDashboardStore } from '../stores/dashboard'

const store = useDashboardStore()
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <h2 style="margin: 0; font-size: 20px;">今日选题</h2>
      <span style="font-size: 13px; color: #888;">{{ store.topics.length }} 个候选</span>
    </div>

    <div v-if="store.topics.length === 0" style="background: white; border-radius: 12px; padding: 40px; text-align: center; color: #999;">
      暂无候选选题，等待 Scout 执行
    </div>

    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px;">
      <div v-for="topic in store.topics" :key="topic.id"
        style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);">

        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <h3 style="margin: 0; font-size: 15px; flex: 1;">{{ topic.title }}</h3>
          <span :style="{
            fontSize: '13px',
            fontWeight: 600,
            color: (topic.final_score || 0) >= 85 ? '#1e7e34' : (topic.final_score || 0) >= 70 ? '#1a73e8' : '#f9a825',
            background: (topic.final_score || 0) >= 85 ? '#e6f4ea' : (topic.final_score || 0) >= 70 ? '#e8f0fe' : '#fff8e1',
            padding: '2px 10px',
            borderRadius: '12px',
          }">
            {{ topic.final_score }}
          </span>
        </div>

        <div style="font-size: 12px; color: #888; margin-bottom: 8px;">
          <span>来源: {{ topic.source }} · </span>
          <span>方向: {{ topic.direction }}</span>
        </div>

        <div v-if="topic.description" style="font-size: 13px; color: #555; margin-bottom: 12px; line-height: 1.5;">
          {{ topic.description.slice(0, 150) }}{{ topic.description.length > 150 ? '...' : '' }}
        </div>

        <!-- Score breakdown -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px;">
          <div v-for="(label, key) in { viral_score: '热度', novelty_score: '新颖', feasibility_score: '可行', saturation_score: '饱和' }" :key="key" style="font-size: 12px;">
            <span style="color: #888;">{{ label }}</span>
            <div style="height: 4px; background: #e0e0e0; border-radius: 2px; margin-top: 2px;">
              <div :style="{ width: ((topic as any)[key] || 0) + '%', height: '100%', background: '#1a73e8', borderRadius: '2px' }"></div>
            </div>
          </div>
        </div>

        <div v-if="topic.url" style="font-size: 12px; margin-bottom: 12px;">
          <a :href="topic.url" target="_blank" style="color: #1a73e8;">原文链接 →</a>
        </div>

        <button @click="store.confirmTopic(topic.id)" style="width: 100%; padding: 8px; background: #1a73e8; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">
          ✅ 确认选题
        </button>
      </div>
    </div>
  </div>
</template>
