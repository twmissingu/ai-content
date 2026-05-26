import { createRouter, createWebHistory } from 'vue-router'
import PipelineView from '../views/PipelineView.vue'
import ApprovalView from '../views/ApprovalView.vue'
import TopicsView from '../views/TopicsView.vue'
import DataView from '../views/DataView.vue'
import KbView from '../views/KbView.vue'

const routes = [
  { path: '/', redirect: '/pipeline' },
  { path: '/pipeline', name: 'Pipeline', component: PipelineView },
  { path: '/approval', name: 'Approval', component: ApprovalView },
  { path: '/topics', name: 'Topics', component: TopicsView },
  { path: '/data', name: 'Data', component: DataView },
  { path: '/kb', name: 'Kb', component: KbView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
