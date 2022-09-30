import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'
import { UseSelect, useSelect } from './useSelect'

type UseCombobox = Omit<UseSelect, 'select'> & {
  combobox: Locator,
  selectCustomOption: (text: string) => Promise<void>,
}

export function useCombobox(locator: string | Locator, page: Page | Locator = PAGE): UseCombobox {
  const { select: combobox, click, selectOption } = useSelect(locator, page)

  const selectCustomOption = async (text: string): Promise<void> => {
    await click()
    await page.locator('.p-combobox__text-input').fill(text)
    await PAGE.keyboard.press('Enter')
    await click()
  }

  return {
    combobox,
    click,
    selectOption,
    selectCustomOption,
  }
}