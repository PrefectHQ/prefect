import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import './registerServiceWorker'
import api from './plugins/api'
import router from './router'
import { VITE_PREFECT_USE_MIRAGEJS } from './utilities/meta'

// Global components
import RadarFlowRunNode from '@/components/Radar/Nodes/FlowRunNode.vue'
import RadarNode from '@/components/Radar/Nodes/Node.vue'
import RadarOverflowNode from '@/components/Radar/Nodes/OverflowNode.vue'

// styles
import '@prefecthq/prefect-design/dist/style.css'
import '@prefecthq/orion-design/dist/style.css'
import '@/styles/main.scss'

const storageKey = 'orion-color-mode'
const storedMode = localStorage.getItem(storageKey)?.toLowerCase()
const defaultClass = 'default-color-mode'
const colorMode = storedMode ? `${storedMode}-color-mode` : defaultClass

document.body.classList.add(colorMode)

async function start(): Promise<void> {
  if (VITE_PREFECT_USE_MIRAGEJS()) {
    const { startServer } = await import('./server')

    startServer()
  }

  const app = createApp(App).use(router).use(api).use(createPinia())

  app.component('RadarNode', RadarNode)
  app.component('RadarFlowRunNode', RadarFlowRunNode)
  app.component('RadarOverflowNode', RadarOverflowNode)


  app.mount('#app')
}

start()