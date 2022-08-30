import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'
import { locate } from './locate'

export type UseIconButtonMenu = {
  menu: Locator,
  selectItem: (text: string) => Promise<void>,
}

export function useIconButtonMenu(locator: string | Locator = '.p-icon-button-menu', page: Page | Locator = PAGE): UseIconButtonMenu {
  const menu = locate(locator, page)

  const selectItem = async (text: string): Promise<void> => {
    await menu.click()
    await PAGE.locator('.p-icon-button-menu__content').locator(`text=${text}`).click()
    await menu.click
  }

  return {
    menu,
    selectItem,
  }
}