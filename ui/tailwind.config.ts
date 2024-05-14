import prefectDesignTailwindConfig from '@prefecthq/prefect-design/src/tailwind.config'
import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './**/*.{vue,js,ts,jsx,tsx}',
  ],
  presets: [prefectDesignTailwindConfig],
}

export default config