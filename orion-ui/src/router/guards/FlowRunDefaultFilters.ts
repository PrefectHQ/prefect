import { Filter } from "@/../packages/orion-design/src/types/filters/index";
import { useFiltersStore } from "@/../packages/orion-design/src/stores/filters";
import { RouteLocationNormalized } from "vue-router";
import { RouteGuard } from "./RouteGuard";

export class FlowRunDefaultFilters implements RouteGuard {
  private readonly filter: Required<Filter> = {
    object: 'flow_run',
    property: 'name',
    type: 'string',
    operation: 'equals',
    value: ''
  }

  public async before(to: RouteLocationNormalized): Promise<void> {
    const filtersInUrl = to.query.filter ?? []
    const filtersStore = useFiltersStore()

    this.filter.value = 'hello world'

    filtersStore.add(this.filter)
  }
}