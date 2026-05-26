<script setup lang="ts">
import { ref, onMounted } from 'vue'

const API_BASE = 'http://localhost:8710'
const costData = ref<any[]>([])
const monthlyTotal = ref(0)

async function fetchCost() {
  try {
    const res = await fetch(`${API_BASE}/api/data/cost`)
    const data = await res.json()
    costData.value = data.daily || []
    monthlyTotal.value = data.monthly_total || 0
  } catch (e) {
    console.error(e)
  }
}

onMounted(fetchCost)

// Simple bar chart using inline styles
function maxCost(): number {
  if (costData.value.length === 0) return 1
  return Math.max(...costData.value.map(d => d.cost), 0.01)
}
</script>

<template>
  <div>
    <h2 style="margin: 0 0 20px 0; font-size: 20px;">数据</h2>

    <!-- Cost card -->
    <div style="background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);">
      <h3 style="margin: 0 0 16px 0; font-size: 15px;">成本消耗</h3>
      <div style="font-size: 28px; font-weight: 600; color: #1a1a2e;">
        ${{ monthlyTotal.toFixed(2) }}
        <span style="font-size: 14px; font-weight: 400; color: #888;">/ 月</span>
      </div>

      <!-- Mini bar chart -->
      <div v-if="costData.length > 0" style="display: flex; align-items: flex-end; gap: 4px; height: 80px; margin-top: 16px;">
        <div v-for="d in costData.slice(-14)" :key="d.date"
          :style="{
            flex: 1,
            height: (d.cost / maxCost() * 70) + 'px',
            background: '#1a73e8',
            borderRadius: '3px 3px 0 0',
            minWidth: '20px',
            position: 'relative',
          }"
          :title="`${d.date}: $${d.cost.toFixed(4)}`">
        </div>
      </div>
      <div v-else style="font-size: 13px; color: #999; margin-top: 16px;">
        暂无成本数据。Writer 执行后会自动记录。
      </div>
    </div>

    <!-- Placeholder for other data -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
      <div style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);">
        <h3 style="margin: 0 0 8px 0; font-size: 15px;">📊 阅读量趋势</h3>
        <p style="font-size: 13px; color: #999;">Phase 3 接入 Feedback 后显示</p>
      </div>
      <div style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);">
        <h3 style="margin: 0 0 8px 0; font-size: 15px;">📈 平台对比</h3>
        <p style="font-size: 13px; color: #999;">Phase 3 接入 Feedback 后显示</p>
      </div>
    </div>
  </div>
</template>
