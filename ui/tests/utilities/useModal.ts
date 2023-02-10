import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

export type UseModal = {
  modal: Locator,
  header: Locator,
  body: Locator,
  footer: Locator,
  close: () => Promise<void>,
  closed: () => Promise<void>,
}

export function useModal(page: Page | Locator = PAGE): UseModal {
  const modal = page.locator('.p-modal')
  const header = modal.locator('.p-modal__header')
  const body = modal.locator('.p-modal__body')
  const footer = modal.locator('.p-modal__footer')
  const close = (): Promise<void> => modal.locator('.p-modal__x-button').click()
  const closed = async (): Promise<void> => await modal.waitFor({ state: 'detached' })

  return {
    modal,
    header,
    body,
    footer,
    close,
    closed,
  }
}