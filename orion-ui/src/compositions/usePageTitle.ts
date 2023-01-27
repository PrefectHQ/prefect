import { computed, Ref, unref, watchEffect } from 'vue'

export function usePageTitle(...pages: (string | Ref<string | null>)[]): void {

  const pagesWithProject = [...pages, 'Prefect Orion']

  const title = computed<string>(() => {
    return pagesWithProject
      .map(page => unref(page))
      .filter(page => page !== null)
      .join(' • ')
  })

  watchEffect(() => document.title = title.value)
}