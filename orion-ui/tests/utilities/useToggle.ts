import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UseToggle = {
  toggle: Locator,
  getState: () => Promise<boolean | undefined>,
  setState: (state: boolean) => Promise<void>,
  waitFor: (state: boolean) => Promise<void>,
}

export function useToggle(page: Page | Locator = PAGE): UseToggle {
  return {
    toggle: getToggle(page),
    getState: (toggle: Locator = getToggle(page)) => {
      return isChecked(toggle)
    },
    setState: async (state, toggle: Locator = getToggle(page)) => {
      const current = await isChecked(toggle)

      if (current !== state) {
        toggle.click()
      }
    },
    waitFor: (state, toggle: Locator = getToggle(page)) => {
      return toggle.locator(`[aria-checked="${state}"]`).waitFor()
    },
  }
}

function getToggle(page: Page | Locator): Locator {
  return page.locator('.p-toggle')
}

async function isChecked(toggle: Locator): Promise<boolean> {
  return await toggle.locator('[aria-checked="true"]').count() === 1
}