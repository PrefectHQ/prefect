import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'
import { locate } from './locate'

export type UseTable = {
  table: Locator,
  rows: Locator,
}

export function useTable(locator: string | Locator = '.p-table', page: Page | Locator = PAGE): UseTable {
  const table = locate(locator, page)
  const rows = table.locator('.p-table-body .p-table-row')

  return {
    table,
    rows,
  }
}