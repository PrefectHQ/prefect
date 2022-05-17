<template>
  <div class="application" data-teleport-target="app">
    <suspense>
      <router-view class="application__router-view" />
    </suspense>
  </div>
</template>

<script lang="ts" setup>
  import { deploymentsApiKey, filtersDefaultObjectKey, flowRunsApiKey, flowsApiKey, logsApiKey, searchApiKey, taskRunsApiKey, workQueuesApiKey, canKey } from '@prefecthq/orion-design'
  import { provide } from 'vue'
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
  provide(filtersDefaultObjectKey, 'flow_run')
  provide(canKey, can)
</script>

<style lang="scss">
.app {
  background-color: var(--grey-10);
  min-height: 100vh;
}

</style>
