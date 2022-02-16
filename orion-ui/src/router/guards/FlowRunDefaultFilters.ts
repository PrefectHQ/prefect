import { useFiltersStore } from "@/../packages/orion-design/src/stores/filters";
import { flowRunsApi } from "@/../packages/orion-design/src/services/FlowRunsApi";
import { RouteLocationNormalized } from "vue-router";
import { RouteGuard } from "@/../packages/orion-design/src/types/RouteGuard";
import { hasFilter } from "@/../packages/orion-design/src/utilities/filters";
import { Filter } from "@/../packages/orion-design/src/types/filters/index";

export class FlowRunDefaultFilters implements RouteGuard {
  public async before(to: RouteLocationNormalized): Promise<void> {
    const filtersStore = useFiltersStore()

    flowRunsApi.getFlowRun(to.params.id as string).then(({ name }) => {
      const defaultFilter: Required<Filter> = {
        object: 'flow_run',
        property: 'name',
        type: 'string',
        operation: 'equals',
        value: name
      }

      if(!hasFilter(filtersStore.all, defaultFilter)) {
        filtersStore.replaceAll([defaultFilter])
      }
    })
  }
}