import { Locator, Page } from '@playwright/test'
import { PAGE } from './fixtures'
import { locate } from './locate'

export type UseForm = {
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