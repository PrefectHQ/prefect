import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import Home from '../views/Home.vue'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'Home',
    component: Home // We don't implement route level code splitting for the home route because we don't want this to load asyncronously
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
