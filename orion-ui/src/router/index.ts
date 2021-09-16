import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard // We don't implement route level code splitting for the Dashboard route because we don't want this to load asyncronously
  },
  {
    path: '/flow-run',
    name: 'FlowRun',
    component: () => import('../views/FlowRun.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/Settings.vue')
  },
  {
    path: '/schematics',
    name: 'Schematics',
    component: () => import('../views/Schematics.vue')
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

export default router
