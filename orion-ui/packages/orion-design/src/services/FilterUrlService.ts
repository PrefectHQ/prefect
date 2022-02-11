import { watch } from 'vue'
import { LocationQuery, LocationQueryValue, Router } from 'vue-router'
import { useFiltersStore } from '../stores/filters'
// import { asArray } from '../utilities/arrays'
import { FilterService } from './FilterService'

export class FilterUrlService {
  private readonly router: Router
  private readonly store = useFiltersStore()
  private unwatch: ReturnType<typeof watch> | null = null

  public constructor(router: Router) {
    this.router = router

    this.updateStore()
    this.start()
  }

  private get query(): LocationQuery {
    return this.router.currentRoute.value.query
  }

  public start(): void {
    this.unwatch = watch(() => this.store.all, () => this.updateUrl())
  }

  public stop(): void {
    if (this.unwatch) {
      this.unwatch()
    }

    this.unwatch = null
  }

  private updateUrl(): void {
    const filters = FilterService.stringify(this.store.all)

    this.router.push({ query: { ...this.query, filter: filters } })
  }

  private updateStore(): void {
    // the this.query is undefined if this happens to early.
    // const filters = asArray(this.query.filters).filter(this.isFilterString)
    const params = new URLSearchParams(window.location.search)
    const filters = params.getAll('filter')
    const parsedFilters = FilterService.parse(filters)

    this.store.replaceAll(parsedFilters)
  }

  private isFilterString(value: LocationQueryValue): value is string {
    if (value === null) {
      return false
    }

    try {
      FilterService.parse(value)
    } catch {
      return false
    }

    return true
  }

}