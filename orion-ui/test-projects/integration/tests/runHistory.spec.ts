import { ui } from '@/utilities/testing'

describe('Dashboard run history', () => {
  it('should show the correct number of bars', async () => {
    const selector = '.run-history-chart__bucket'

    await page.goto(ui)
    await page.waitForSelector(selector)

    const bars = await page.$$(selector)

    expect(bars.length).toBe(29)
  })
})
