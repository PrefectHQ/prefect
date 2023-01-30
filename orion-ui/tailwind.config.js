/* eslint-disable @typescript-eslint/no-require-imports */
/* eslint-disable @typescript-eslint/no-var-requires */
const prefectDesignPlugin = require('@prefecthq/prefect-design/dist/tailwindPlugin.js')

module.exports = {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  plugins: [prefectDesignPlugin],
}