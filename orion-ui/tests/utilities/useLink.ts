import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UseLink = {
  link: Locator,
}

export function useLink(href: string, page: Page | Locator = PAGE): UseLink {
  const link = page.locator(`[href="${href}"]`)

  return {
    link,
  }
}