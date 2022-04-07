import { LocationQuery, Router } from 'vue-router'
import { FilterService } from '@/services/FilterService'
import { FilterState, useFiltersStore } from '@/stores/filters'
import { Filter, FilterObject } from '@/types/filters'
import { hasFilter } from '@/utilities/filters'

export class FilterUrlService {
  private readonly router: Router
  private readonly store = useFiltersStore()

  public constructor(router: Router) {
    this.router = router
  }

  private get query(): LocationQuery {
    return this.router.currentRoute.value.query
  }

  public add(filter: Required<Filter>): void {
    if (hasFilter(this.store.all, filter)) {
      return
    }

    this.store.add(filter)
    this.updateUrl()
  }

  public remove(filter: FilterState): void {
    this.store.remove(filter)
    this.updateUrl()
  }

  public removeAll(): void {
    this.store.removeAll()
    this.updateUrl()
  }

  public replaceAll(filters: Required<Filter>[]): void {
    this.store.replaceAll(filters)
    this.updateUrl()
  }

  public updateStore(defaultObject: FilterObject): void {
    const params = new URLSearchParams(window.location.search)
    const filters = params.getAll('filter')
    const parsedFilters = FilterService.parse(filters, defaultObject)

    this.store.replaceAll(parsedFilters)
  }

  private updateUrl(): void {
    const filters = FilterService.stringify(this.store.all, { method: 'short' })

    this.router.push({ query: { ...this.query, filter: filters } })
  }

}