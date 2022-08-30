import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'
import { useLink } from './useLink'

export type UseContextSidebar = {
  sidebar: Locator,
  navigate: (destination: string) => Promise<void>,
}

export function useContextSidebar(page: Page | Locator = PAGE): UseContextSidebar {
  const sidebar = page.locator('.app__sidebar')

  return {
    sidebar,
    navigate: async (destination) => {
      const { link } = useLink(destination, sidebar)
      link.click()

      await PAGE.waitForNavigation({
        url: route => route.pathname === destination,
      })
    },
  }
}