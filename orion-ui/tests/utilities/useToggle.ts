import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UseToggle = {
  toggle: Locator,
  getState: () => Promise<boolean | undefined>,
  setState: (state: boolean) => Promise<void>,
}

export function useToggle(page: Page | Locator = PAGE): UseToggle {
  return {
    toggle: getToggle(page),
    getState: async (toggle: Locator = getToggle(page)) => {
      const count = await toggle.count()
      console.log({ count })
      const promises: Promise<boolean>[] = []

      for (let i = 0; i < count; ++i) {
        promises.push(getToggleState(toggle.nth(i)))
      }

      const states = await Promise.all(promises)
      if (new Set(states).size === 1) {
        return states[0]
      }
    },
    setState: async (state, toggle: Locator = getToggle(page)) => {
      const count = await toggle.count()
      const promises: Promise<void>[] = []

      for (let i = 0; i < count; ++i) {
        promises.push(setToggleState(toggle.nth(i), state))
      }

      await Promise.all(promises)
    },
  }
}

function getToggle(page: Page | Locator): Locator {
  return page.locator('.p-toggle')
}

async function setToggleState(toggle: Locator, state: boolean): Promise<void> {
  const current = await getToggleState(toggle)

  if (current !== state) {
    await toggle.click()
    await toggle.locator(`[aria-checked="${state}"]`).waitFor()
  }
}

async function getToggleState(toggle: Locator): Promise<boolean> {
  return await toggle.locator('[aria-checked="true"]').count() === 1
}