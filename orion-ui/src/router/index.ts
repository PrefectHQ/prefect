import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import { FilterUrlService } from '@/../packages/orion-design/src/services'
import { DashboardDefaultFilters } from './guards/DashboardDefaultFilters'
import { FlowRunDefaultFilters } from './guards/FlowRunDefaultFilters'
import { RouteGuardExecutor } from './guards/RouteGuardExecutor'
import { GlobalLoadFiltersFromRoute } from './guards/GlobalLoadFiltersFromRoute'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard, // We don't implement route level code splitting for the Dashboard route because we don't want this to load asyncronously
    meta: {
      guards: [new DashboardDefaultFilters()] 
    }
  },
  {
    path: '/flow-run/:id',
    name: 'FlowRun',
    component: () => import('../views/FlowRun.vue'),
    meta: {
      guards: [ new FlowRunDefaultFilters()]
    },
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

RouteGuardExecutor.register(new GlobalLoadFiltersFromRoute(router))

router.beforeEach(async (to, from) => {
  return await RouteGuardExecutor.before(to, from)
})

router.afterEach(async (to, from) => {
  return await RouteGuardExecutor.after(to, from)
})

export default router
