import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UseLabel = {
  label: Locator,
  control: Locator,
}

export function useLabel(text: string, page: Page | Locator = PAGE): UseLabel {
  const label = page.locator('.p-label', {
    has: page.locator('.p-label__label', {
      hasText: text,
    }),
  })

  const control = label.locator('.p-label__body')

  return {
    label,
    control,
  }
}