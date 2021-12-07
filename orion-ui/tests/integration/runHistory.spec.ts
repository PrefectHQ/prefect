// todo: this needs to be abstracted out into a utility
const ui = `http://localhost:${process.env.ORION_UI_PORT}`

describe('Dashboard run history', () => {
  it('should show the correct number of bars', async () => {
    const selector = '.run-history-chart__bucket'

    await page.goto(ui)
    await page.waitForSelector(selector)

    const bars = await page.$$(selector)

    expect(bars.length).toBe(29)
  })
})
