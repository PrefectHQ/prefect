import { LocationQuery, LocationQueryValue, Router } from 'vue-router'
import { FilterState, useFiltersStore } from '../stores/filters'
import { Filter } from '../types/filters'
import { FilterService } from './FilterService'

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

  public updateStore(): void {
    const params = new URLSearchParams(window.location.search)
    const filters = params.getAll('filter')
    const parsedFilters = FilterService.parse(filters)

    this.store.replaceAll(parsedFilters)
  }

  private updateUrl(): void {
    const filters = FilterService.stringify(this.store.all)

    this.router.push({ query: { ...this.query, filter: filters } })
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