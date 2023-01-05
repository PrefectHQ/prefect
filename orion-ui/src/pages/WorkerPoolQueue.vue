<template>
  <p-layout-default v-if="workerPoolQueue" class="worker-pool-queue">
    <template #header>
      <PageHeadingWorkerPoolQueue :worker-pool-queue="workerPoolQueue" :worker-pool-name="workerPoolName" @update="workerPoolQueuesSubscription.refresh" />
    </template>

    <p-layout-well class="worker-pool-queue__body">
      <template #header>
        <CodeBanner :command="workerPoolQueueCliCommand" title="Worker pool queue is ready to go!" subtitle="Work queues are scoped to a specific work pool to ensure that the work put into a queue will only be picked up by a specific type of worker." />
      </template>

      <p-tabs :tabs="tabs">
        <template #details>
          <WorkerPoolQueueDetails :worker-pool-name="workerPoolName" :worker-pool-queue="workerPoolQueue" />
        </template>

        <template #upcoming-runs>
          <WorkerPoolQueueUpcomingFlowRunsList :worker-pool-name="workerPoolName" :worker-pool-queue="workerPoolQueue" />
        </template>

        <template #runs>
          <FlowRunFilteredList :flow-run-filter="flowRunFilter" />
        </template>
      </p-tabs>

      <template #well>
        <WorkerPoolQueueDetails alternate :worker-pool-name="workerPoolName" :worker-pool-queue="workerPoolQueue" />
      </template>
    </p-layout-well>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkerPoolQueue, CodeBanner, WorkerPoolQueueDetails, WorkerPoolQueueUpcomingFlowRunsList, useFlowRunFilter, FlowRunFilteredList } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useRouteParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const workerPoolName = useRouteParam('workerPoolName')
  const workerPoolQueueName = useRouteParam('workerPoolQueueName')
  const subscriptionOptions = {
    interval: 300000,
  }

  const workerPoolQueuesSubscription = useSubscription(api.workerPoolQueues.getWorkerPoolQueueByName, [workerPoolName.value, workerPoolQueueName.value], subscriptionOptions)
  const workerPoolQueue = computed(() => workerPoolQueuesSubscription.response)

  const workerPoolWorkersSubscription = useSubscription(api.workerPoolWorkers.getWorkers, [workerPoolName.value], subscriptionOptions)
  const workerPoolWorkers = computed(() => workerPoolWorkersSubscription.response ?? [])
  const workerPoolWorkerName = computed(() => workerPoolWorkers.value[0]?.name ?? '<worker name>')

  const workerPoolQueueCliCommand = computed(() => `prefect worker start --pool ${workerPoolName.value} --name ${workerPoolWorkerName.value} *--queue ${workerPoolQueueName.value}`)

  const flowRunFilter = useFlowRunFilter({ workerPoolQueueName: [workerPoolQueueName.value] })

  const tabs = computed(() => {
    const values = ['Upcoming Runs', 'Runs']

    if (!media.xl) {
      values.unshift('Details')
    }

    return values
  })

  const title = computed(() => {
    if (!workerPoolQueueName.value) {
      return 'Worker Pool Queue'
    }
    return `Worker Pool Queue: ${workerPoolQueueName.value}`
  })

  usePageTitle(title)
</script>

<style>
/* This is an override since this is using nested layouts */
.worker-pool-queue__body {
  @apply
  p-0
}
</style>