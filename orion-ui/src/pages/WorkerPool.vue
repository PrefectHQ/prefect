<template>
  <p-layout-default v-if="workerPool" class="worker-pool">
    <template #header>
      <PageHeadingWorkerPool :worker-pool="workerPool" />
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkerPool } from '@prefecthq/orion-design'
  import { useRouteParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'

  const api = useWorkspaceApi()
  const workerPoolName = useRouteParam('workerPoolName')

  const subscriptionOptions = {
    interval: 300000,
  }
  const workerPoolSubscription = useSubscription(api.workerPools.getWorkerPoolByName, [workerPoolName.value], subscriptionOptions)
  const workerPool = computed(() => workerPoolSubscription.response)
</script>