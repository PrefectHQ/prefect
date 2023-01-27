import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UseToggle = {
  toggle: Locator,
}

export function useToggle(page: Page | Locator = PAGE): UseToggle {
  const toggle = page.locator('.p-toggle__control')

  return {
    toggle,
  }
}