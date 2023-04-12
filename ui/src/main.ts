import { plugin as PrefectDesign } from '@prefecthq/prefect-design'
import { plugin as PrefectUILibrary } from '@prefecthq/prefect-ui-library'
import { createApp } from 'vue'
import router from '@/router'
import { initColorMode } from '@/utilities/colorMode'

// styles
import '@prefecthq/vue-charts/dist/style.css'
import '@prefecthq/prefect-design/dist/style.css'
import '@prefecthq/prefect-ui-library/dist/style.css'
import '@/styles/style.css'

// We want components imported last because import order determines style order
// eslint-disable-next-line import/order
import App from '@/App.vue'

initColorMode()

function start(): void {
  const app = createApp(App)

  app.use(router)
  app.use(PrefectDesign)
  app.use(PrefectUILibrary)

  app.mount('#app')
}

start()