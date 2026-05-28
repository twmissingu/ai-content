import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/pipeline' },
  { path: '/pipeline', name: 'Pipeline', component: () => import('../views/PipelineView.vue') },
  { path: '/approval', name: 'Approval', component: () => import('../views/ApprovalView.vue') },
  { path: '/topics', name: 'Topics', component: () => import('../views/TopicsView.vue') },
  { path: '/data', name: 'Data', component: () => import('../views/DataView.vue') },
  { path: '/kb', name: 'Kb', component: () => import('../views/KbView.vue') },
  { path: '/config', name: 'Config', component: () => import('../views/ConfigView.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
