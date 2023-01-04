<template>
  <p-layout-well v-if="workerPool" class="worker-pool">
    <template #header>
      <PageHeadingWorkerPool :worker-pool="workerPool" @update="workerPoolSubscription.refresh" />
    </template>

    <p-tabs :tabs="tabs">
      <template #details>
        <WorkerPoolDetails :worker-pool="workerPool" />
      </template>

      <template #runs>
        <FlowRunFilteredList :flow-run-filter="flowRunFilter" />
      </template>

      <template #queues>
        <WorkerPoolQueuesTable :worker-pool-name="workerPoolName" />
      </template>

      <template #workers>
        <WorkersTable :worker-pool-filter="workerPool.name" />
      </template>
    </p-tabs>

    <template #well>
      <WorkerPoolDetails alternate :worker-pool="workerPool" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkerPool, WorkerPoolDetails, WorkersTable, useRecentFlowRunFilter, FlowRunFilteredList, WorkerPoolQueuesTable } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useRouteParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

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
  const workerPoolId = computed(() => workerPool.value ? [workerPool.value.id] : [])

  const flowRunFilter = useRecentFlowRunFilter({ workerPools: workerPoolId })

  const title = computed(() => {
    if (!workerPool.value) {
      return 'Worker Pool'
    }
    return `Worker Pool: ${workerPool.value.name}`
  })

  usePageTitle(title)
</script>