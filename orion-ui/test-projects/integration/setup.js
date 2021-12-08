const { setup: setupDevServer } = require('jest-dev-server')
const { setup: setupPuppeteer } = require('jest-environment-puppeteer')
const { port, uri } = require('../../src/utilities/testing')
const puppeteer = require('puppeteer')
const cyan = '\x1b[36m%s\x1b[0m'

const warmUpVite = async function () {
  console.log('\n')
  console.log(cyan, 'Warming up vite...', '\n')

  const browser = await puppeteer.launch()
  const page = await browser.newPage()

  await page.goto(uri)
  await page.waitForSelector('.application')

  await browser.close()

  console.log(cyan, 'Toasty!', '\n')
}

module.exports = async function globalSetup(globalConfig) {
  await setupPuppeteer(globalConfig)

  await setupDevServer({
    command: `vite --port ${port} --strict-port`,
    launchTimeout: 10000,
    port
  })

  await warmUpVite()
}
