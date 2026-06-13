<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import SkeletonLoader from '../components/SkeletonLoader.vue'
import { useKeyboardShortcut, isInputElement } from '../composables/useKeyboardShortcut'
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
import { API_BASE } from '../utils/api'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

const store = useDashboardStore()
const costData = ref<any[]>([])
const monthlyTotal = ref(0)
const loading = ref(true)



async function fetchCost() {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/data/cost`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
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
    backgroundColor: 'rgba(77, 100, 117, 0.58)',
    borderColor: 'rgba(77, 100, 117, 0.92)',
    borderWidth: 1,
    borderRadius: 6,
    hoverBackgroundColor: 'rgba(77, 100, 117, 0.72)',
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
      backgroundColor: 'rgba(36, 33, 29, 0.88)',
      titleColor: '#fffdf8',
      bodyColor: '#fffdf8',
      titleFont: {
        size: 12,
      },
      bodyFont: {
        size: 14,
        weight: 'bold' as const,
      },
      padding: 12,
      cornerRadius: 10,
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
        color: 'rgba(98, 93, 85, 0.82)',
      },
    },
    y: {
      beginAtZero: true,
      grid: {
        color: 'rgba(92, 79, 62, 0.08)',
      },
      ticks: {
        font: {
          size: 11,
        },
        color: 'rgba(98, 93, 85, 0.82)',
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

// ── Keyboard shortcuts ──────────────────────────────────────────────
function handleKeydown(e: KeyboardEvent) {
  if (isInputElement(e.target)) return
  if (e.key === 'r' || e.key === 'R') {
    fetchCost()
  }
}

useKeyboardShortcut(handleKeydown)
</script>

<template>
  <div class="data-view">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title">数据分析</h2>
        <p class="page-subtitle">成本消耗与内容表现</p>
      </div>
      <button class="btn btn-ghost btn-sm" @click="fetchCost" aria-label="刷新数据">
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
            <div class="progress-bar" role="progressbar" :aria-valuenow="Math.round(budgetStatus.percentage)" aria-valuemin="0" aria-valuemax="100" :aria-label="`预算使用 ${budgetStatus.percentage.toFixed(0)}%`">
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

    <!-- Keyboard Shortcuts Hint -->
    <div class="keyboard-hints" role="region" aria-label="快捷键说明">
      <div class="hint-item"><kbd>R</kbd><span>刷新</span></div>
    </div>
  </div>
</template>

<style scoped>
.data-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-2xl);
}

/* ── Page Header ─────────────────────────────────────────────── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-lg);
  padding: var(--space-xl);
  background: rgba(255, 253, 248, 0.58);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-2xl);
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: 650;
  color: var(--text-primary);
  letter-spacing: -0.025em;
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
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: var(--space-lg);
}

.stat-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-lg);
  background: var(--surface-glow);
  transition: border-color var(--transition-normal), box-shadow var(--transition-normal), transform var(--transition-normal);
}

.stat-card:hover {
  border-color: var(--border-color);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.stat-icon {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  flex: 0 0 auto;
  border-radius: var(--radius-xl);
  background: rgba(248, 244, 236, 0.72);
  font-size: var(--text-2xl);
  line-height: 1;
  opacity: 0.76;
  filter: grayscale(0.18);
}

.stat-content { flex: 1; }

.stat-label {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-bottom: var(--space-xs);
}

.stat-value {
  font-size: var(--text-3xl);
  font-weight: 750;
  color: var(--text-primary);
  line-height: 1.18;
  letter-spacing: -0.03em;
}

.stat-unit {
  font-size: var(--text-md);
  font-weight: 450;
  color: var(--text-tertiary);
}

.stat-progress {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-top: var(--space-md);
}

.stat-progress .progress-bar { flex: 1; }

.progress-text {
  font-size: var(--text-sm);
  font-weight: 650;
  color: var(--text-secondary);
  min-width: 36px;
  text-align: right;
}

.stat-hint {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-top: var(--space-sm);
}

/* ── Stat Card Tints ────────────────────────────────────────── */
.cost-card { background: linear-gradient(135deg, rgba(255, 253, 248, 0.96), rgba(239, 246, 236, 0.76)); }
.articles-card { background: linear-gradient(135deg, rgba(255, 253, 248, 0.96), rgba(238, 243, 245, 0.78)); }
.topics-card { background: linear-gradient(135deg, rgba(255, 253, 248, 0.96), rgba(250, 244, 231, 0.82)); }

.stat-link {
  font-size: var(--text-sm);
  color: var(--primary-dark);
  text-decoration: none;
  font-weight: 600;
}

.stat-link:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}

/* ── Chart Card ──────────────────────────────────────────────── */
.chart-card,
.platform-card {
  background: var(--surface-glow);
}

.chart-card {
  min-height: 320px;
}

.chart-card .card-header,
.platform-card .card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.chart-container {
  height: 260px;
  padding: var(--space-md);
}

/* ── Loading State ───────────────────────────────────────────── */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  height: 210px;
  color: var(--text-tertiary);
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Empty / Placeholder State ───────────────────────────────── */
.empty-chart,
.placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 210px;
  gap: var(--space-sm);
  background-image: var(--paper-grain);
  background-size: 8px 8px;
}

.empty-icon,
.placeholder-icon {
  font-size: 44px;
  opacity: 0.5;
  filter: grayscale(0.18);
}

.empty-text {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-secondary);
}

.empty-hint,
.placeholder-text {
  font-size: var(--text-md);
  color: var(--text-tertiary);
  text-align: center;
}

/* ── Platform Cards ──────────────────────────────────────────── */
.platforms-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-lg);
}

.placeholder-content {
  padding: var(--space-3xl);
  border-radius: var(--radius-xl);
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
  .page-header { flex-direction: column; }

  .stats-grid {
    grid-template-columns: 1fr 1fr;
  }

  .platforms-grid {
    grid-template-columns: 1fr;
  }

  .chart-container {
    height: 220px;
  }
}

@media (max-width: 480px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
