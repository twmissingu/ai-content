<script setup lang="ts">
import { ref } from 'vue'

const API_BASE = 'http://localhost:8710'
const query = ref('')
const results = ref<any[]>([])
const sections = ref<any[]>([])
const searched = ref(false)

async function search() {
  if (!query.value.trim()) return
  searched.value = true
  try {
    const res = await fetch(`${API_BASE}/api/kb/search?q=${encodeURIComponent(query.value)}`)
    const data = await res.json()
    results.value = data.results
  } catch (e) {
    console.error(e)
  }
}

async function fetchSections() {
  try {
    const res = await fetch(`${API_BASE}/api/kb/sections`)
    const data = await res.json()
    sections.value = data.sections
  } catch (e) {
    console.error(e)
  }
}

fetchSections()
</script>

<template>
  <div>
    <h2 style="margin: 0 0 20px 0; font-size: 20px;">知识库</h2>

    <!-- Search bar -->
    <div style="display: flex; gap: 8px; margin-bottom: 20px;">
      <input
        v-model="query"
        @keyup.enter="search"
        placeholder="搜索知识库..."
        style="flex: 1; padding: 10px 16px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; outline: none;">
      <button @click="search" style="padding: 10px 24px; background: #1a73e8; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px;">搜索</button>
    </div>

    <!-- Sections overview -->
    <div style="display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap;">
      <div v-for="s in sections" :key="s.name"
        style="background: white; border-radius: 8px; padding: 12px 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); display: flex; align-items: center; gap: 8px;">
        <span style="font-size: 13px; color: #555;">{{ s.name }}</span>
        <span style="font-size: 12px; color: #888;">({{ s.count }})</span>
      </div>
    </div>

    <!-- Search results -->
    <div v-if="searched && results.length === 0" style="background: white; border-radius: 12px; padding: 20px; text-align: center; color: #999;">
      未找到匹配结果
    </div>

    <div v-for="r in results" :key="r.path"
      style="background: white; border-radius: 8px; padding: 16px; margin-bottom: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);">
      <div style="font-size: 14px; font-weight: 500;">{{ r.title }}</div>
      <div style="font-size: 12px; color: #888; margin-top: 4px;">
        <span>{{ r.type }} / </span>
        <span>{{ r.path }}</span>
      </div>
      <div v-if="r.match" style="font-size: 13px; color: #555; margin-top: 8px; background: #f8f9fa; padding: 8px; border-radius: 4px;">
        ...{{ r.match }}...
      </div>
    </div>
  </div>
</template>
