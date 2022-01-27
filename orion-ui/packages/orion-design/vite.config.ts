import { resolve } from 'path'
import vue from '@vitejs/plugin-vue'
import { defineConfig, UserConfig } from 'vite'

// eslint-disable-next-line import/no-default-export
export default defineConfig(({ mode }: { mode: string }) => {
  function isFolder(mode: string): boolean {
    return ['components', 'models', 'services', 'utilities'].includes(mode)
  }

  const entry = resolve(__dirname, isFolder(mode) ? `src/${mode}/index.ts` : 'src/index.ts')
  const name = isFolder(mode) ? `Orion Design ${mode}` : 'Orion Design'

  function fileName(format: string): string {
    return isFolder(mode) ? `orion-design-${mode}.${format}.js` : `orion-design.${format}.js`
  }

  const options: UserConfig = {
    resolve: {
      alias: [
        {
          find: '@',
          replacement: resolve(__dirname, '../../src'),
        },
      ],
    },
    plugins: [vue()],
    build: {
      emptyOutDir: false,
      lib: {
        entry,
        name,
        fileName,
      },
      rollupOptions: {
        external: ['vue'],
        output: {
          exports: 'named',
          globals: {
            vue: 'Vue',
          },
        },
      },
    },
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: `
          @use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;
          `,
        },
      },
    },
  }

  return options
})
