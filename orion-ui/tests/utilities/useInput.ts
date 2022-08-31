import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UseInput = {
  input: Locator,
}

export function useInput(page: Page | Locator = PAGE): UseInput {
  const input = page.locator('input')

  return {
    input,
  }
}