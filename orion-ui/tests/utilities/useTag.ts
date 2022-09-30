import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UseTag = {
  tag: Locator,
}

export function useTag(text: string, page: Page | Locator = PAGE): UseTag {
  const tag = page.locator('.p-tag', {
    hasText: text,
  })

  return {
    tag,
  }
}