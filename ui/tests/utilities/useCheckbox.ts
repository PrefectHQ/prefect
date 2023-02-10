import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UseCheckbox = {
  checkbox: Locator,
}

export function useCheckbox(label: string, page: Page | Locator = PAGE): UseCheckbox {
  const checkbox = page.locator('.p-checkbox', {
    has: page.locator('.p-checkbox__label', {
      hasText: label,
    }),
  }).locator('[type="checkbox"]')

  return {
    checkbox,
  }
}