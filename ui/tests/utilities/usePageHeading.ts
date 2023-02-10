import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UsePageHeading = {
  heading: Locator,
}

export function usePageHeading(text: string = '', page: Page | Locator = PAGE): UsePageHeading {
  const heading = page.locator('.page-heading', {
    has: page.locator('.page-heading__crumbs', {
      hasText: text,
    }),
  })

  return {
    heading,
  }
}