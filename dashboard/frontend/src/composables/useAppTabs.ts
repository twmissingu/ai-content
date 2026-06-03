/**
 * Tab configuration and navigation for the app shell.
 * Extracted from App.vue to keep the root component slim.
 */

import { useRoute } from 'vue-router'

export interface AppTab {
  name: string
  label: string
  icon: string
  path: string
  badge?: boolean
}

export function useAppTabs() {
  const route = useRoute()

  const tabs: AppTab[] = [
    { name: 'Pipeline', label: '管线', icon: '📊', path: '/pipeline' },
    { name: 'Approval', label: '审批', icon: '📋', path: '/approval', badge: true },
    { name: 'Topics', label: '选题', icon: '🔥', path: '/topics' },
    { name: 'Data', label: '数据', icon: '📈', path: '/data' },
    { name: 'Kb', label: '知识库', icon: '🗄️', path: '/kb' },
    { name: 'Sources', label: '信源', icon: '📡', path: '/sources' },
    { name: 'Config', label: '配置', icon: '⚙️', path: '/config' },
  ]

  function isActive(tab: AppTab): boolean {
    return route.path === tab.path
  }

  return { tabs, isActive }
}
