import { Filter } from "@/../packages/orion-design/src/types/filters/index";
import { useFiltersStore } from "@/../packages/orion-design/src/stores/filters";
import { RouteLocationNormalized } from "vue-router";
import { RouteGuard } from "./RouteGuard";

export class DashboardDefaultFilters implements RouteGuard {
  private readonly filters: Required<Filter>[] = [
    {
      object: 'flow_run',
      property: 'start_date',
      type: 'date',
      operation: 'newer',
      value: '1d'
    },
    {
      object: 'flow_run',
      property: 'start_date',
      type: 'date',
      operation: 'upcoming',
      value: '1d'
    }
  ]

  public before(to: RouteLocationNormalized): void {
    const filtersInRoute = to.query.filter ?? []

    if(filtersInRoute.length == 0) {
      const filtersStore = useFiltersStore()

      filtersStore.replaceAll(this.filters)
    }
  }
}