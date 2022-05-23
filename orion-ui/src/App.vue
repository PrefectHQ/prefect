<template>
  <div class="app" data-teleport-target="app">
    <ContextSidebar />
    <suspense>
      <router-view class="application__router-view" />
    </suspense>
  </div>
</template>

<script lang="ts" setup>
  import {
    deploymentsApiKey,
    flowRunsApiKey,
    flowsApiKey,
    logsApiKey,
    searchApiKey,
    taskRunsApiKey,
    workQueuesApiKey,
    canKey,
    ContextSidebar,
    flowRunsRouteKey,
    flowsRouteKey,
    deploymentsRouteKey,
    queuesRouteKey,
    settingsRouteKey
  } from '@prefecthq/orion-design'
  import { provide } from 'vue'
  import { routes } from '@/router/routes'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { flowsApi } from '@/services/flowsApi'
  import { logsApi } from '@/services/logsApi'
  import { searchApi } from '@/services/searchApi'
  import { taskRunsApi } from '@/services/taskRunsApi'
  import { workQueuesApi } from '@/services/workQueuesApi'
  import { can } from '@/utilities/permissions'

  provide(deploymentsApiKey, deploymentsApi)
  provide(flowRunsApiKey, flowRunsApi)
  provide(flowsApiKey, flowsApi)
  provide(logsApiKey, logsApi)
  provide(searchApiKey, searchApi)
  provide(taskRunsApiKey, taskRunsApi)
  provide(workQueuesApiKey, workQueuesApi)
  provide(canKey, can)
  provide(flowRunsRouteKey, routes.flowRuns)
  provide(flowsRouteKey, routes.flows)
  provide(deploymentsRouteKey, routes.deployments)
  provide(queuesRouteKey, routes.queues)
  provide(settingsRouteKey, routes.settings)
</script>

<style lang="scss">
.app { @apply
  bg-slate-200
  text-slate-900;
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
}
</style>
