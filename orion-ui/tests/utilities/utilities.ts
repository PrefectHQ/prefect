import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'

function locate(stringOrLocator: string | Locator, page: Page | Locator = PAGE): Locator {
  if (typeof stringOrLocator === 'string') {
    return page.locator(stringOrLocator)
  }

  return stringOrLocator
}

type UseLabel = {
  label: Locator,
  control: Locator,
}

export function useLabel(text: string, page: Page | Locator = PAGE): UseLabel {
  const label = page.locator('.p-label', {
    has: page.locator('.p-label__label', {
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

export function useSelect(locator: string | Locator, page: Page | Locator = PAGE): UseSelect {
  const select = locate(locator, page)

  const click = async (): Promise<void> => await select.click({
    position: {
      x: 5,
      y: 5,
    },
  })

  const selectOption = async (text: string): Promise<void> => {
    await click()
    await PAGE.locator('.p-select-options').locator(`text=${text}`).click()
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

export function useCombobox(locator: string | Locator, page: Page | Locator = PAGE): UseCombobox {
  const { select: combobox, click, selectOption } = useSelect(locator, page)

  const selectCustomOption = async (text: string): Promise<void> => {
    await click()
    await page.locator('.p-combobox__text-input').fill(text)
    await PAGE.keyboard.press('Enter')
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

export function useButton(text: string, page: Page | Locator = PAGE): UseButton {
  const button = page.locator('.p-button', {
    hasText: text,
  })

  return {
    button,
  }
}

type UseTable = {
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

type UseForm = {
  form: Locator,
  footer: Locator,
  submit: () => Promise<void>,
}

export function useForm(locator: string | Locator = '.p-form', page: Page | Locator = PAGE): UseForm {
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

type UseCheckbox = {
  checkbox: Locator,
}

export function useCheckbox(label: string, page: Page | Locator = PAGE): UseCheckbox {
  const checkbox = page.locator('.p-checkbox', {
    has: page.locator('.p-checkbox__label', {
      hasText: label,
    }),
  }).locator('[type="checkbox"]')

  return {
    checkbox,
  }
}

type UseLink = {
  link: Locator,
}

export function useLink(href: string, page: Page | Locator = PAGE): UseLink {
  const link = page.locator(`[href="${href}"]`)

  return {
    link,
  }
}

type UseIconButtonMenu = {
  menu: Locator,
  selectItem: (text: string) => void,
}

export function useIconButtonMenu(locator: string | Locator = '.p-icon-button-menu', page: Page | Locator = PAGE): UseIconButtonMenu {
  const menu = locate(locator, page)

  const selectItem = async (text: string): Promise<void> => {
    await menu.click()
    await PAGE.locator('.p-icon-button-menu__content').locator(`text=${text}`).click()
    await menu.click
  }

  return {
    menu,
    selectItem,
  }
}

type UseTag = {
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

type UseModal = {
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