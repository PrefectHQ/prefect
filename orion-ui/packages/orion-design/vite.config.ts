import { defineConfig } from 'vite'

import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  resolve: {
    alias: [
      {
        find: '@',
        replacement: resolve(__dirname, '../../src')
      }
    ]
  },
  plugins: [vue()],
  build: {
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      name: 'Orion Design',
      fileName: (format) => `orion-design.${format}.js`
    },
    rollupOptions: {
      external: ['vue'],
      output: {
        exports: 'named',
        globals: {
          vue: 'Vue'
        }
      }
    }
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
