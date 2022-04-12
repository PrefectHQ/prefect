import { Filter, useFiltersStore, RouteGuard } from '@prefecthq/orion-design'
import { RouteLocationNormalized } from 'vue-router'

export class DashboardDefaultFilters implements RouteGuard {
  private readonly filters: Required<Filter>[] = [
    {
      object: 'flow_run',
      property: 'start_date',
      type: 'date',
      operation: 'last',
      value: '1d',
    },
    {
      object: 'flow_run',
      property: 'start_date',
      type: 'date',
      operation: 'next',
      value: '1d',
    },
  ]

  public before(to: RouteLocationNormalized): void {
    const filtersInRoute = to.query.filter ?? []

    if (filtersInRoute.length == 0) {
      const filtersStore = useFiltersStore()

      filtersStore.replaceAll(this.filters)
    }
  }
}