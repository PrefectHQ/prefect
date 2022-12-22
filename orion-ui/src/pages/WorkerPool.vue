<template>
  <p-layout-well v-if="workerPool" class="worker-pool">
    <template #header>
      <PageHeadingWorkerPool :worker-pool="workerPool" />
    </template>

    <p-tabs :tabs="tabs">
      <template #details>
        <WorkerPoolDetails :worker-pool="workerPool" />
      </template>

      <template #runs>
        Runs
        <!-- <WorkerPoolRunFilteredList :worker-pool-filter="workerPoolFilter" /> -->
      </template>

      <template #queues>
        Queues
        <!-- <WorkerPoolQueueFilteredList :worker-pool-filter="workerPoolFilter" /> -->
      </template>

      <template #workers>
        Workers
        <!-- <WorkerPoolWorkerFilteredList :worker-pool-filter="workerPoolFilter" /> -->
      </template>
    </p-tabs>

    <template #well>
      <WorkerPoolDetails :worker-pool="workerPool" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkerPool, WorkerPoolDetails } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useRouteParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'

  const api = useWorkspaceApi()
  const workerPoolName = useRouteParam('workerPoolName')

  const tabs = computed(() => {
    const values = ['Runs', 'Queues', 'Workers']

    if (!media.xl) {
      values.unshift('Details')
    }

    return values
  })

  const subscriptionOptions = {
    interval: 300000,
  }
  const workerPoolSubscription = useSubscription(api.workerPools.getWorkerPoolByName, [workerPoolName.value], subscriptionOptions)
  const workerPool = computed(() => workerPoolSubscription.response)
</script>