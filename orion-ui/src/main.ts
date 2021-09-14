import { createApp } from 'vue'
import App from './App.vue'
import './registerServiceWorker'
import router from './router'
import store from './store'

// Imports global miter styles
import '@prefect/miter-design/dist/style.css'

// import '@/styles/main.scss'

// Note: this is a locally-installed package, relative to this directory at ../
import MiterDesign from '@prefect/miter-design'

const storageKey = 'orion-color-mode'
const storedMode = localStorage.getItem(storageKey)?.toLowerCase()
const defaultClass = 'default-color-mode'
const colorMode = storedMode ? storedMode + '-color-mode' : defaultClass
document.body.classList.add(colorMode)

const app = createApp(App).use(MiterDesign).use(store).use(router)

app.mount('#app')
