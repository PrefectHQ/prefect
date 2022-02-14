import { useFiltersStore } from "@/../packages/orion-design/src/stores/filters";
import { flowRunsApi } from "@/../packages/orion-design/src/services/FlowRunsApi";
import { RouteLocationNormalized } from "vue-router";
import { RouteGuard } from "./RouteGuard";

export class FlowRunDefaultFilters implements RouteGuard {
  public async before(to: RouteLocationNormalized): Promise<void> {
    const filtersStore = useFiltersStore()

    flowRunsApi.getFlowRun(to.params.id as string).then(({ name }) => {
      filtersStore.add({
        object: 'flow_run',
        property: 'name',
        type: 'string',
        operation: 'equals',
        value: name
      })
    })
  }
}