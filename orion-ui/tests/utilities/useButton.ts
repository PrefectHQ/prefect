import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UseButton = {
  button: Locator,
}

export function useButton(text: string, page: Page | Locator = PAGE): UseButton {
  const button = page.locator('.p-button', {
    hasText: text,
  })

  return {
    button,
  }
}