import { test as base, Page } from '@playwright/test'

export let PAGE: Page

export const test = base.extend({
  page: async ({ page }, use) => {
    PAGE = page
    await use(page)
  },
})