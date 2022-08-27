import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UseToggle = {
  toggle: Locator,
}

export function useToggle(page: Page | Locator = PAGE): UseToggle {
  return {
    toggle: getToggle(page),
  }
}

function getToggle(page: Page | Locator): Locator {
  return page.locator('.p-toggle__control')
}