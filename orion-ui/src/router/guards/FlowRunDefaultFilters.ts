import { Filter, useFiltersStore, RouteGuard, hasFilter } from '@prefecthq/orion-design'
import { RouteLocationNormalized } from 'vue-router'
import { flowRunsApi } from '@/services/flowRunsApi'

export class FlowRunDefaultFilters implements RouteGuard {
  public before(to: RouteLocationNormalized): void {
    const filtersStore = useFiltersStore()

    flowRunsApi.getFlowRun(to.params.id as string).then(({ name }) => {
      const defaultFilter: Required<Filter> = {
        object: 'flow_run',
        property: 'name',
        type: 'string',
        operation: 'equals',
        value: name!,
      }

      if (!hasFilter(filtersStore.all, defaultFilter)) {
        filtersStore.replaceAll([defaultFilter])
      }
    })
  }
}