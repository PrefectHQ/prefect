import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import { FilterUrlService } from '@/../packages/orion-design/src/services'

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
        path: 'radar',
        component: () => import('../views/FlowRun--views/Radar.vue')
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
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.afterEach((to, from) => {
  if(to.query.filter !== from.query.filter) {
    const service = new FilterUrlService(router)
    
    service.updateStore()
  }
})

export default router
