import prefectDesignTailwindConfig from '@prefecthq/prefect-design/src/tailwind.config'
import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.vue',
  ],
  presets: [prefectDesignTailwindConfig],
}

export default config