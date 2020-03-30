import Router from 'vue-router'
import NotFoundPage from '@/pages/NotFoundPage.vue'
import multiguard from 'vue-router-multiguard'

export const routes = [
  {
    name: 'not-found',
    path: '/404',
    beforeEnter: multiguard([]),
    component: NotFoundPage
  },
  {
    name: 'api',
    path: '/api',
    component: () =>
      import(
        /* webpackChunkName: "interactive-api" */ '@/pages/InteractiveAPI/InteractiveAPI.vue'
      ),
    beforeEnter: multiguard([])
  },
  {
    name: 'schematics',
    path: '/schematics',
    component: () =>
      import(
        /* webpackChunkName: "schematics" */ '@/pages/Schematics/Schematics.vue'
      ),
    beforeEnter: multiguard([]),
    redirect: { name: 'schematic' },
    children: [
      {
        name: 'schematic',
        path: 'schematic/:id?',
        component: () =>
          import(
            /* webpackChunkName: "schematics--view" */ '@/pages/Schematics/View.vue'
          ),
        beforeEnter: multiguard([])
      }
    ]
  },
  {
    name: 'flow',
    path: '/flow/:id',
    component: () =>
      import(/* webpackChunkName: "flow" */ '@/pages/Flow/Flow.vue'),
    beforeEnter: multiguard([])
  },
  {
    name: 'run-flow',
    path: '/flow/:id/run',
    redirect: { name: 'flow', query: { run: '' } }
  },
  {
    name: 'flow-run',
    path: '/flow-run/:id',
    component: () =>
      import(/* webpackChunkName: "flow-run" */ '@/pages/FlowRun/FlowRun.vue'),
    beforeEnter: multiguard([])
  },
  {
    name: 'flow-run-logs',
    path: '/flow-run/:id/logs',
    redirect: { name: 'flow-run', query: { logId: '' } }
  },
  {
    name: 'task',
    path: '/task/:id',
    component: () =>
      import(/* webpackChunkName: "task" */ '@/pages/Task/Task.vue'),
    beforeEnter: multiguard([])
  },
  {
    name: 'task-run',
    path: '/task-run/:id',
    component: () =>
      import(/* webpackChunkName: "task-run" */ '@/pages/TaskRun/TaskRun.vue'),
    beforeEnter: multiguard([])
  },
  {
    name: 'flow-version-groups',
    path: '/flow-version-groups',
    component: () =>
      import(
        /* webpackChunkName: "flow-version-groups" */ '@/pages/FlowVersionGroups/FlowVersionGroups.vue'
      )
  },
  {
    path: '/welcome',
    component: () =>
      import(
        /* webpackChunkName: "onboard-page" */ '@/pages/Onboard/Onboard-Page.vue'
      ),
    beforeEnter: multiguard([]),
    children: [
      {
        name: 'welcome',
        path: '',
        component: () =>
          import(
            /* webpackChunkName: "welcome" */ '@/pages/Onboard/Welcome.vue'
          )
      }
    ]
  },
  {
    name: 'dashboard',
    alias: '/',
    path: '/',
    component: () =>
      import(
        /* webpackChunkName: "dashboard" */ '@/pages/Dashboard/Dashboard.vue'
      ),
    beforeEnter: multiguard([])
  },
  {
    path: '*',
    redirect: '404'
  }
]

const router = new Router({
  mode: 'history',
  routes
})

export default router
