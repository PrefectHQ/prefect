import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export function locate(stringOrLocator: string | Locator, page: Page | Locator = PAGE): Locator {
  if (typeof stringOrLocator === 'string') {
    return page.locator(stringOrLocator)
  }

  return stringOrLocator
}