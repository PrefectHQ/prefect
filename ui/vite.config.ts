import { resolve } from 'path'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const base = mode == 'development' ? '' : '/PREFECT_UI_SERVE_BASE_REPLACE_PLACEHOLDER'

  return {
    plugins: [vue()],
    base,
    resolve: {
      alias: [{ find: '@', replacement: resolve(__dirname, './src') }],
      dedupe: ['vue', 'vue-router'],
    },
    build: {
      sourcemap: true,
    },
  }
})
