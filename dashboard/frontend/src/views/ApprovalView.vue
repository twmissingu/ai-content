<script setup lang="ts">
import { ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'

const store = useDashboardStore()
const selectedId = ref<string | null>(null)
const rejectReason = ref('')
const showRejectInput = ref<string | null>(null)

function select(id: string) {
  selectedId.value = selectedId.value === id ? null : id
}

function doReject(id: string) {
  if (!rejectReason.value.trim()) return
  store.reject(id, rejectReason.value)
  showRejectInput.value = null
  rejectReason.value = ''
}
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <h2 style="margin: 0; font-size: 20px;">审批队列</h2>
      <span style="font-size: 13px; color: #888;">{{ store.approvalQueue.length }} 篇待审</span>
    </div>

    <div v-if="store.approvalQueue.length === 0" style="background: white; border-radius: 12px; padding: 40px; text-align: center; color: #999;">
      暂无待审批文章
    </div>

    <div v-for="article in store.approvalQueue" :key="article.id"
      style="background: white; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);">

      <div style="display: flex; justify-content: space-between; align-items: flex-start; cursor: pointer;" @click="select(article.id)">
        <div>
          <h3 style="margin: 0 0 4px 0; font-size: 16px;">{{ article.meta.topic }}</h3>
          <div style="font-size: 12px; color: #888;">
            <span>评分: {{ article.meta.proofread_score }} · </span>
            <span>修订: {{ article.meta.revised_rounds }} 轮 · </span>
            <span>字数: {{ article.meta.word_count }}</span>
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button @click.stop="store.approve(article.id)" style="padding: 6px 16px; background: #1e7e34; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">✅ 通过</button>
          <button v-if="showRejectInput !== article.id" @click.stop="showRejectInput = article.id" style="padding: 6px 16px; background: #c5221f; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">❌ 驳回</button>
        </div>
      </div>

      <!-- Reject input -->
      <div v-if="showRejectInput === article.id" style="margin-top: 12px; display: flex; gap: 8px;">
        <input v-model="rejectReason" placeholder="驳回原因..." style="flex: 1; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px;">
        <button @click="doReject(article.id)" :disabled="!rejectReason.trim()" style="padding: 6px 16px; background: #c5221f; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">确认驳回</button>
        <button @click="showRejectInput = null; rejectReason = ''" style="padding: 6px 16px; background: #eee; color: #555; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">取消</button>
      </div>

      <!-- Content preview (expandable) -->
      <div v-if="selectedId === article.id" style="margin-top: 16px; padding: 16px; background: #f8f9fa; border-radius: 8px; font-size: 13px; line-height: 1.6; max-height: 400px; overflow-y: auto; white-space: pre-wrap;">
        {{ article.meta.topic ? '#' + article.meta.topic : '' }}
        {{ article.content_preview }}
      </div>
    </div>
  </div>
</template>
