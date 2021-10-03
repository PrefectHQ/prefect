import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard // We don't implement route level code splitting for the Dashboard route because we don't want this to load asyncronously
  },
  {
    path: '/flow-run/:id',
    name: 'FlowRun',
    component: () => import('../views/FlowRun.vue'),
    children: [
      {
        path: '',
        component: () => import('../views/FlowRun--views/Index.vue')
      },
      {
        path: 'timeline',
        component: () => import('../views/FlowRun--views/Timeline.vue')
      },
      {
        path: 'schematic',
        component: () => import('../views/FlowRun--views/Schematic.vue')
      }
    ]
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/Settings.vue')
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

export default router
