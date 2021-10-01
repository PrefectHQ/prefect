import { createApp } from 'vue'
import App from './App.vue'
import './registerServiceWorker'
import router from './router'
import store from './store'
import api from './plugins/api'

// Global components
import ButtonCard from '@/components/Global/Button--Card/Button--Card.vue'
import ButtonRounded from '@/components/Global/Button--Rounded/Button--Rounded.vue'
import BreadCrumbs from '@/components/Global/BreadCrumb/BreadCrumb.vue'
import Drawer from '@/components/Global/Drawer/Drawer.vue'
import List from '@/components/Global/List/List.vue'
import ListItem from '@/components/Global/List/ListItem/ListItem.vue'
import ListItemDeployment from '@/components/Global/List/ListItem--Deployment/ListItem--Deployment.vue'
import ListItemFlow from '@/components/Global/List/ListItem--Flow/ListItem--Flow.vue'
import ListItemFlowRun from '@/components/Global/List/ListItem--FlowRun/ListItem--FlowRun.vue'
import ListItemTaskRun from '@/components/Global/List/ListItem--TaskRun/ListItem--TaskRun.vue'
import ResultsList from '@/components/Global/ResultsLists/ResultsList.vue'
import Row from '@/components/Global/Row/Row.vue'

// Note: this is a locally-installed package, relative to this directory at ../
import '@prefect/miter-design/dist/style.css'
import MiterDesign from '@prefect/miter-design'

import '@/styles/main.scss'

const storageKey = 'orion-color-mode'
const storedMode = localStorage.getItem(storageKey)?.toLowerCase()
const defaultClass = 'default-color-mode'
const colorMode = storedMode ? storedMode + '-color-mode' : defaultClass
document.body.classList.add(colorMode)

const app = createApp(App).use(MiterDesign).use(store).use(router).use(api)

app.component('button-card', ButtonCard)
app.component('bread-crumbs', BreadCrumbs)
app.component('rounded-button', ButtonRounded)
app.component('drawer', Drawer)
app.component('list', List)
app.component('list-item', ListItem)
app.component('deployment-list-item', ListItemDeployment)
app.component('flow-list-item', ListItemFlow)
app.component('flow-run-list-item', ListItemFlowRun)
app.component('task-run-list-item', ListItemTaskRun)
app.component('results-list', ResultsList)
app.component('row', Row)

app.mount('#app')
