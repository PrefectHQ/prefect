import { uri } from '@/utilities/testing'

describe('Dashboard run history', () => {
  it('should show the correct number of bars', async () => {
    const selector = '.run-history-chart__bucket'

    await page.goto(uri)
    await page.waitForSelector(selector)

    const bars = await page.$$(selector)

    expect(bars.length).toBe(29)
  })
})
