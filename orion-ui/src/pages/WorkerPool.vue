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
        <FlowRunFilteredList :flow-run-filter="flowRunFilter" />
      </template>

      <template #queues>
        Queues
        <!-- <WorkerPoolQueueFilteredList :worker-pool-filter="workerPoolFilter" /> -->
        <template v-if="workerPoolQueues.length">
          <li v-for="queue in workerPoolQueues" :key="queue.name">
            <p-link :to="routes.workerPoolQueue(workerPool.name, queue.name)">
              <span>{{ queue.name }}</span>
            </p-link>
          </li>
        </template>


        <!--
          <template #name="{ row }">
          <p-link :to="routes.workQueue(row.id)">
          <span>{{ row.name }}</span>
          </p-link>
          </template>
        -->
      </template>

      <template #workers>
        <WorkersTable :worker-pool-filter="workerPool.name" />
      </template>
    </p-tabs>

    <template #well>
      <WorkerPoolDetails :worker-pool="workerPool" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkerPool, WorkerPoolDetails, WorkersTable, useRecentFlowRunFilter, FlowRunFilteredList } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useRouteParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { routes } from '@/router'

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

  const workerPoolQueuesSubscription = useSubscription(api.workerPoolQueues.getWorkerPoolQueues, [workerPoolName.value], subscriptionOptions)
  const workerPoolQueues = computed(() => workerPoolQueuesSubscription.response ?? [])

  const flowRunFilter = useRecentFlowRunFilter({ workerPoolQueues: workerPoolQueues.value.map(queue => queue.id) })
</script>