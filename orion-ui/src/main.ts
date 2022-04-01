import MiterDesign from '@prefecthq/miter-design'
import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import './registerServiceWorker'
import api from './plugins/api'
import router from './router'
import { VITE_PREFECT_USE_MIRAGEJS } from './utilities/meta'

// Global components
import ButtonRounded from '@/components/Global/ButtonRounded/ButtonRounded.vue'
import List from '@/components/Global/List/List.vue'
import ListItem from '@/components/Global/List/ListItem/ListItem.vue'
import ListItemDeployment from '@/components/Global/List/ListItemDeployment/ListItemDeployment.vue'
import ListItemFlow from '@/components/Global/List/ListItemFlow/ListItemFlow.vue'
import ListItemFlowRun from '@/components/Global/List/ListItemFlowRun/ListItemFlowRun.vue'
import ListItemSubFlowRun from '@/components/Global/List/ListItemSubFlowRun/ListItemSubFlowRun.vue'
import ListItemTaskRun from '@/components/Global/List/ListItemTaskRun/ListItemTaskRun.vue'
import ResultsList from '@/components/Global/ResultsList/ResultsList.vue'
import Row from '@/components/Global/Row/Row.vue'
import StateIcon from '@/components/Global/StateIcon/StateIcon.vue'
import RadarFlowRunNode from '@/components/Radar/Nodes/FlowRunNode.vue'
import RadarNode from '@/components/Radar/Nodes/Node.vue'
import RadarOverflowNode from '@/components/Radar/Nodes/OverflowNode.vue'

// styles
import '@prefecthq/miter-design/dist/style.css'
import '@prefecthq/orion-design/dist/style.css'
import '@/styles/main.scss'

const storageKey = 'orion-color-mode'
const storedMode = localStorage.getItem(storageKey)?.toLowerCase()
const defaultClass = 'default-color-mode'
const colorMode = storedMode ? `${storedMode }-color-mode` : defaultClass
document.body.classList.add(colorMode)

async function start(): Promise<void> {
  if (VITE_PREFECT_USE_MIRAGEJS()) {
    const { startServer } = await import('./server')

    startServer()
  }

  const app = createApp(App).use(MiterDesign).use(router).use(api).use(createPinia())

  app.component('ButtonRounded', ButtonRounded)
  app.component('List', List)
  app.component('ListItem', ListItem)
  app.component('ListItemDeployment', ListItemDeployment)
  app.component('ListItemFlow', ListItemFlow)
  app.component('ListItemFlowRun', ListItemFlowRun)
  app.component('ListItemSubFlowRun', ListItemSubFlowRun)
  app.component('ListItemTaskRun', ListItemTaskRun)
  app.component('ResultsList', ResultsList)
  app.component('Row', Row)
  app.component('RadarNode', RadarNode)
  app.component('RadarFlowRunNode', RadarFlowRunNode)
  app.component('RadarOverflowNode', RadarOverflowNode)
  app.component('StateIcon', StateIcon)

  app.mount('#app')
}

start()