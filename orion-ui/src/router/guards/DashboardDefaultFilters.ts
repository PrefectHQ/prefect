import { Filter } from "@/../packages/orion-design/src/types/filters/index";
import { useFiltersStore } from "@/../packages/orion-design/src/stores/filters";
import { RouteLocationNormalized } from "vue-router";
import { RouteGuard } from "./RouteGuard";

export class DashboardDefaultFilters implements RouteGuard {
  private readonly filters: Required<Filter>[] = [
    {
      object: 'flow_run',
      property: 'start_date',
      type: 'time',
      operation: 'newer',
      value: '1d'
    },
    {
      object: 'flow_run',
      property: 'start_date',
      type: 'time',
      operation: 'older',
      value: '-1d'
    }
  ]

  public before(to: RouteLocationNormalized): void {
    const filtersInUrl = to.query.filter ?? []

    if(filtersInUrl.length == 0) {
      const filtersStore = useFiltersStore()

      filtersStore.replaceAll(this.filters)
    }
  }
}