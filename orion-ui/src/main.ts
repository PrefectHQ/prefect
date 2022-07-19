import { plugin as OrionDesign } from '@prefecthq/orion-design'
import { plugin as PrefectDesign } from '@prefecthq/prefect-design'
import { createPinia } from 'pinia'
import { createApp } from 'vue'
import router from './router'
import { applyActiveColorModeClass } from './utilities/colorMode'

// styles
import '@prefecthq/prefect-design/dist/style.css'
import '@prefecthq/orion-design/dist/style.css'
import '@/styles/style.css'

// We want components imported last because import order determines style order
// eslint-disable-next-line import/order
import App from './App.vue'

applyActiveColorModeClass()

function start(): void {
  const app = createApp(App)

  app.use(router)
  app.use(createPinia())
  app.use(PrefectDesign)
  app.use(OrionDesign)

  app.mount('#app')
}

start()