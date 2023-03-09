import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'
import { locate } from './locate'

export type UseSelect = {
  select: Locator,
  selectOption: (text: string) => Promise<void>,
  click: () => Promise<void>,
}

export function useSelect(locator: string | Locator, page: Page | Locator = PAGE): UseSelect {
  const select = locate(locator, page)

  const click = async (): Promise<void> => await select.click({
    position: {
      x: 5,
      y: 5,
    },
  })

  const selectOption = async (text: string): Promise<void> => {
    await click()
    await PAGE.locator('.p-select-options').locator(`text=${text}`).click()
    await click()
  }

  return {
    select,
    click,
    selectOption,
  }
}