import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export function prefectMirage() {
  return {
    name: 'prefect-mirage-server',
    transform(src, id) {
      const useMirageJs = process.env.PREFECT_USE_MIRAGEJS ?? false

      if (useMirageJs && id.endsWith('src/main.ts')) {
        return {
          code: `${src}\nimport { startServer } from './server'\nstartServer()`
        }
      }
    }
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), prefectMirage()],
  base: process.env['ORION_UI_SERVE_BASE'] || '',
  resolve: {
    alias: [{ find: '@', replacement: resolve(__dirname, './src') }]
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `
        @use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;
        `
      }
    }
  }
})
