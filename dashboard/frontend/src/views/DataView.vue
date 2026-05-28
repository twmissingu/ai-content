<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import SkeletonLoader from '../components/SkeletonLoader.vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

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

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

const recentCosts = computed(() => costData.value.slice(-14))

const chartData = computed(() => ({
  labels: recentCosts.value.map(d => formatDate(d.date)),
  datasets: [{
    label: '每日成本 ($)',
    data: recentCosts.value.map(d => d.cost),
    backgroundColor: 'rgba(26, 115, 232, 0.6)',
    borderColor: 'rgba(26, 115, 232, 1)',
    borderWidth: 1,
    borderRadius: 4,
    hoverBackgroundColor: 'rgba(26, 115, 232, 0.8)',
  }],
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      titleFont: {
        size: 12,
      },
      bodyFont: {
        size: 14,
        weight: 'bold' as const,
      },
      padding: 12,
      cornerRadius: 8,
      callbacks: {
        label: (context: any) => `$${context.parsed.y.toFixed(4)}`,
      },
    },
  },
  scales: {
    x: {
      grid: {
        display: false,
      },
      ticks: {
        font: {
          size: 11,
        },
        color: 'rgba(0, 0, 0, 0.5)',
      },
    },
    y: {
      beginAtZero: true,
      grid: {
        color: 'rgba(0, 0, 0, 0.05)',
      },
      ticks: {
        font: {
          size: 11,
        },
        color: 'rgba(0, 0, 0, 0.5)',
        callback: (value: any) => `$${value}`,
      },
    },
  },
}))

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

    <!-- Loading Skeletons -->
    <div v-if="loading" class="stats-grid">
      <div v-for="i in 2" :key="i" class="card stat-card-skeleton" style="padding: 20px;">
        <SkeletonLoader type="title" width="50%" />
        <SkeletonLoader type="text" width="80%" />
        <SkeletonLoader type="card" height="24px" />
      </div>
    </div>

    <!-- Stats Cards -->
    <div v-else class="stats-grid">
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

      <!-- Article Count Card -->
      <div class="card stat-card articles-card">
        <div class="stat-icon">📝</div>
        <div class="stat-content">
          <div class="stat-label">待审批文章</div>
          <div class="stat-value">
            {{ store.pendingCount }}
            <span class="stat-unit">篇</span>
          </div>
          <div class="stat-hint">
            <router-link to="/approval" class="stat-link">前往审批 →</router-link>
          </div>
        </div>
      </div>

      <!-- Topics Count Card -->
      <div class="card stat-card topics-card">
        <div class="stat-icon">🔥</div>
        <div class="stat-content">
          <div class="stat-label">候选选题</div>
          <div class="stat-value">
            {{ store.topics.length }}
            <span class="stat-unit">个</span>
          </div>
          <div class="stat-hint">
            <router-link to="/topics" class="stat-link">查看选题 →</router-link>
          </div>
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
        <Bar
          :data="chartData"
          :options="chartOptions"
        />
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
  transition: all var(--transition-normal);
}

.stat-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
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

.articles-card {
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--primary-light) 100%);
}

.topics-card {
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--warning-light) 100%);
}

.stat-hint {
  margin-top: var(--space-sm);
}

.stat-link {
  font-size: var(--text-sm);
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
}

.stat-link:hover {
  text-decoration: underline;
}

/* ── Chart Card ──────────────────────────────────────────────── */
.chart-card {
  min-height: 300px;
}

.chart-container {
  height: 250px;
  padding: var(--space-md);
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

  .chart-container {
    height: 200px;
  }
}

@media (max-width: 480px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
