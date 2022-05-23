import { plugin as PrefectDesign } from '@prefecthq/prefect-design'
import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import './registerServiceWorker'
import router from './router'
import { VITE_PREFECT_USE_MIRAGEJS } from './utilities/meta'

// styles
import '@prefecthq/prefect-design/dist/style.css'
import '@prefecthq/orion-design/dist/style.css'
import '@/styles/style.css'

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

  const app = createApp(App)

  app.use(router)
  app.use(createPinia())
  app.use(PrefectDesign)

  app.mount('#app')
}

start()