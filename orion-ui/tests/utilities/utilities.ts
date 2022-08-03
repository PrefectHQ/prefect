import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

function locate(stringOrLocator: string | Locator, page: Page = PAGE): Locator {
  if (typeof stringOrLocator === 'string') {
    return page.locator(stringOrLocator)
  }

  return stringOrLocator
}

type UseLabel = {
  label: Locator,
  control: Locator,
}

export function useLabel(text: string, page: Page = PAGE): UseLabel {
  const label = page.locator('.p-label', {
    has: page.locator('.p-label__text', {
      hasText: text,
    }),
  })

  const control = label.locator('.p-label__body')

  return {
    label,
    control,
  }
}

type UseSelect = {
  select: Locator,
  selectOption: (text: string) => Promise<void>,
  click: () => Promise<void>,
}

export function useSelect(locator: string | Locator, page: Page = PAGE): UseSelect {
  const select = locate(locator, page)

  const click = async (): Promise<void> => await select.click({
    position: {
      x: 5,
      y: 5,
    },
  })

  const selectOption = async (text: string): Promise<void> => {
    await click()
    await page.locator('.p-select-options').locator(`text=${text}`).click()
    await click()
  }

  return {
    select,
    click,
    selectOption,
  }
}

type UseCombobox = Omit<UseSelect, 'select'> & {
  combobox: Locator,
  selectCustomOption: (text: string) => Promise<void>,
}

export function useCombobox(locator: string | Locator, page: Page = PAGE): UseCombobox {
  const { select: combobox, click, selectOption } = useSelect(locator, page)

  const selectCustomOption = async (text: string): Promise<void> => {
    await click()
    await page.locator('.p-combobox__text-input').fill(text)
    await page.keyboard.press('Enter')
    await click()
  }

  return {
    combobox,
    click,
    selectOption,
    selectCustomOption,
  }
}

type UseButton = {
  button: Locator,
}

export function useButton(text: string, page: Page = PAGE): UseButton {
  const button = page.locator('.p-button', {
    has: page.locator('.p-button__content', {
      hasText: text,
    }),
  })

  return {
    button,
  }
}

type UseTable = {
  table: Locator,
  rows: Locator,
}

export function useTable(locator: string | Locator, page: Page = PAGE): UseTable {
  const table = locate(locator, page)
  const rows = table.locator('.p-table-body .p-table-row')

  return {
    table,
    rows,
  }
}

type UseForm = {
  form: Locator,
  footer: Locator,
  submit: () => Promise<void>,
}

export function useForm(locator: string | Locator, page: Page = PAGE): UseForm {
  const form = locate(locator, page)
  const footer = form.locator('.p-form__footer')
  const submit = async (): Promise<void> => await footer.locator('[type="submit"]').click()

  return {
    form,
    footer,
    submit,
  }
}

type UsePageHeading = {
  heading: Locator,
}

export function usePageHeading(locator: string | Locator = '.page-heading', page: Page = PAGE): UsePageHeading {
  const heading = locate(locator, page)

  return {
    heading,
  }
}