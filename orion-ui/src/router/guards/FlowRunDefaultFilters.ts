import { Filter, useFiltersStore, RouteGuard } from '@prefecthq/orion-design'
import { flowRunsApi } from '@prefecthq/orion-design/services'
import { hasFilter } from '@prefecthq/orion-design/utilities'
import { RouteLocationNormalized } from 'vue-router'

export class FlowRunDefaultFilters implements RouteGuard {
  public async before(to: RouteLocationNormalized): Promise<void> {
    const filtersStore = useFiltersStore()

    flowRunsApi.getFlowRun(to.params.id as string).then(({ name }) => {
      const defaultFilter: Required<Filter> = {
        object: 'flow_run',
        property: 'name',
        type: 'string',
        operation: 'equals',
        value: name,
      }

      if (!hasFilter(filtersStore.all, defaultFilter)) {
        filtersStore.replaceAll([defaultFilter])
      }
    })
  }
}