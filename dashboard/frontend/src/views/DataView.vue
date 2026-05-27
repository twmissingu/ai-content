<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'

const store = useDashboardStore()
const costData = ref<any[]>([])
const monthlyTotal = ref(0)
const loading = ref(true)

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

async function fetchCost() {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/data/cost`)
    const data = await res.json()
    costData.value = data.daily || []
    monthlyTotal.value = data.monthly_total || 0
  } catch (e) {
    console.error('Failed to fetch cost data:', e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchCost)

function maxCost(): number {
  if (costData.value.length === 0) return 1
  return Math.max(...costData.value.map(d => d.cost), 0.01)
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

const recentCosts = computed(() => costData.value.slice(-14))

const budgetStatus = computed(() => {
  const budget = store.config?.budget
  if (!budget) return null
  return {
    limit: budget.monthly_limit_usd || 15,
    percentage: (monthlyTotal.value / (budget.monthly_limit_usd || 15)) * 100,
    isWarning: monthlyTotal.value / (budget.monthly_limit_usd || 15) > 0.8,
  }
})
</script>

<template>
  <div class="data-view">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title">数据分析</h2>
        <p class="page-subtitle">成本消耗与内容表现</p>
      </div>
      <button class="btn btn-ghost btn-sm" @click="fetchCost">
        <span>🔄</span> 刷新
      </button>
    </div>

    <!-- Stats Cards -->
    <div class="stats-grid">
      <!-- Monthly Cost Card -->
      <div class="card stat-card cost-card">
        <div class="stat-icon">💰</div>
        <div class="stat-content">
          <div class="stat-label">本月成本</div>
          <div class="stat-value">
            ${{ monthlyTotal.toFixed(2) }}
            <span class="stat-unit">/ 月</span>
          </div>
          <div v-if="budgetStatus" class="stat-progress">
            <div class="progress-bar">
              <div 
                class="progress-bar-fill"
                :class="{
                  success: budgetStatus.percentage < 60,
                  warning: budgetStatus.percentage >= 60 && budgetStatus.percentage < 80,
                  danger: budgetStatus.percentage >= 80
                }"
                :style="{ width: Math.min(budgetStatus.percentage, 100) + '%' }"
              ></div>
            </div>
            <span class="progress-text">{{ budgetStatus.percentage.toFixed(0) }}%</span>
          </div>
        </div>
      </div>

      <!-- Placeholder Cards -->
      <div class="card stat-card placeholder-card">
        <div class="stat-icon">📊</div>
        <div class="stat-content">
          <div class="stat-label">文章总数</div>
          <div class="stat-value text-tertiary">--</div>
          <div class="stat-hint">Phase 3 启用</div>
        </div>
      </div>

      <div class="card stat-card placeholder-card">
        <div class="stat-icon">👀</div>
        <div class="stat-content">
          <div class="stat-label">总阅读量</div>
          <div class="stat-value text-tertiary">--</div>
          <div class="stat-hint">Phase 3 启用</div>
        </div>
      </div>

      <div class="card stat-card placeholder-card">
        <div class="stat-icon">📈</div>
        <div class="stat-content">
          <div class="stat-label">平均互动率</div>
          <div class="stat-value text-tertiary">--</div>
          <div class="stat-hint">Phase 3 启用</div>
        </div>
      </div>
    </div>

    <!-- Cost Chart -->
    <div class="card chart-card">
      <div class="card-header">
        <h3 class="card-title">📊 每日成本趋势</h3>
        <span class="card-subtitle">最近 14 天</span>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="loading-state">
        <div class="loading-spinner"></div>
        <span>加载中...</span>
      </div>

      <!-- Chart -->
      <div v-else-if="recentCosts.length > 0" class="chart-container">
        <div class="chart-bars">
          <div 
            v-for="d in recentCosts" 
            :key="d.date" 
            class="chart-bar-wrapper"
          >
            <div class="chart-bar-tooltip">
              <div class="tooltip-date">{{ d.date }}</div>
              <div class="tooltip-value">${{ d.cost.toFixed(4) }}</div>
            </div>
            <div 
              class="chart-bar"
              :style="{ height: (d.cost / maxCost() * 100) + '%' }"
            ></div>
            <div class="chart-bar-label">{{ formatDate(d.date) }}</div>
          </div>
        </div>
        <div class="chart-y-axis">
          <span>${{ maxCost().toFixed(3) }}</span>
          <span>${{ (maxCost() / 2).toFixed(3) }}</span>
          <span>$0</span>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="empty-chart">
        <div class="empty-icon">📈</div>
        <div class="empty-text">暂无成本数据</div>
        <div class="empty-hint">Writer 执行后会自动记录</div>
      </div>
    </div>

    <!-- Platform Comparison -->
    <div class="platforms-grid">
      <div class="card platform-card">
        <div class="card-header">
          <h3 class="card-title">📊 阅读量趋势</h3>
        </div>
        <div class="placeholder-content">
          <div class="placeholder-icon">📉</div>
          <div class="placeholder-text">Phase 3 接入 Feedback 后显示</div>
        </div>
      </div>

      <div class="card platform-card">
        <div class="card-header">
          <h3 class="card-title">📈 平台对比</h3>
        </div>
        <div class="placeholder-content">
          <div class="placeholder-icon">📊</div>
          <div class="placeholder-text">Phase 3 接入 Feedback 后显示</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.data-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

/* ── Page Header ─────────────────────────────────────────────── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-xs) 0;
}

.page-subtitle {
  font-size: var(--text-md);
  color: var(--text-tertiary);
  margin: 0;
}

/* ── Stats Grid ──────────────────────────────────────────────── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-lg);
}

.stat-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-lg);
}

.stat-icon {
  font-size: var(--text-4xl);
  line-height: 1;
  opacity: 0.8;
}

.stat-content {
  flex: 1;
}

.stat-label {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-bottom: var(--space-xs);
}

.stat-value {
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-unit {
  font-size: var(--text-md);
  font-weight: 400;
  color: var(--text-tertiary);
}

.stat-progress {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-top: var(--space-md);
}

.stat-progress .progress-bar {
  flex: 1;
}

.progress-text {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 36px;
  text-align: right;
}

.stat-hint {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-top: var(--space-xs);
}

/* ── Cost Card ───────────────────────────────────────────────── */
.cost-card {
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--success-light) 100%);
}

/* ── Chart Card ──────────────────────────────────────────────── */
.chart-card {
  min-height: 300px;
}

.chart-container {
  display: flex;
  gap: var(--space-lg);
  height: 200px;
  padding-top: var(--space-lg);
}

.chart-bars {
  flex: 1;
  display: flex;
  align-items: flex-end;
  gap: var(--space-sm);
  height: 100%;
}

.chart-bar-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  position: relative;
}

.chart-bar {
  width: 100%;
  min-height: 4px;
  background: linear-gradient(180deg, var(--primary) 0%, var(--primary-light) 100%);
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  transition: height var(--transition-slow);
  cursor: pointer;
}

.chart-bar:hover {
  opacity: 0.8;
}

.chart-bar-tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--text-primary);
  color: white;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  font-size: var(--text-xs);
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--transition-fast);
}

.chart-bar-wrapper:hover .chart-bar-tooltip {
  opacity: 1;
}

.tooltip-date {
  font-weight: 500;
  margin-bottom: 2px;
}

.tooltip-value {
  color: var(--success-light);
}

.chart-bar-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-top: var(--space-sm);
  white-space: nowrap;
}

.chart-y-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  min-width: 48px;
  text-align: right;
}

/* ── Loading State ───────────────────────────────────────────── */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  height: 200px;
  color: var(--text-tertiary);
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Empty State ─────────────────────────────────────────────── */
.empty-chart {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: var(--space-sm);
}

.empty-icon {
  font-size: 48px;
  opacity: 0.5;
}

.empty-text {
  font-size: var(--text-lg);
  font-weight: 500;
  color: var(--text-secondary);
}

.empty-hint {
  font-size: var(--text-md);
  color: var(--text-tertiary);
}

/* ── Platform Cards ──────────────────────────────────────────── */
.platforms-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-lg);
}

.placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-3xl);
  gap: var(--space-md);
}

.placeholder-icon {
  font-size: 48px;
  opacity: 0.5;
}

.placeholder-text {
  font-size: var(--text-md);
  color: var(--text-tertiary);
  text-align: center;
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr 1fr;
  }
  
  .platforms-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
