<script setup lang="ts">
/**
 * ApprovalPublishPanel — publish button and integration for approval articles.
 * Extracted from ApprovalView.vue to reduce its size.
 */
import { ref } from 'vue'
import { useToast } from '../composables/useToast'
import { API_BASE } from '../utils/api'

const props = defineProps<{
  articleId: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  published: []
}>()

const toast = useToast()
const publishing = ref(false)

async function publishArticle() {
  publishing.value = true
  try {
    
    const res = await fetch(`${API_BASE}/api/approval/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        article_id: props.articleId,
        platforms: ['wechat', 'xiaohongshu', 'douyin'],
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    toast.success(`发布已触发: ${data.platforms?.join(', ')}`)
    emit('published')
  } catch (e) {
    toast.error(`发布失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    publishing.value = false
  }
}
</script>

<template>
  <div class="publish-section">
    <button
      class="btn btn-primary btn-sm"
      :disabled="disabled || publishing"
      :aria-label="`发布文章 ${articleId}`"
      @click="publishArticle"
    >
      🚀 {{ publishing ? '发布中...' : '发布到平台' }}
    </button>
  </div>
</template>

<style scoped>
.publish-section {
  margin-top: var(--space-md);
  padding-top: var(--space-md);
  border-top: 1px solid var(--divider);
  display: flex;
  gap: var(--space-md);
}
</style>
