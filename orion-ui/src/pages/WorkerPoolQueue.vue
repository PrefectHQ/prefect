<template>
  <p-layout-well v-if="workerPoolQueue" class="worker-pool">
    <template #header>
      <PageHeadingWorkerPoolQueue :worker-pool-queue="workerPoolQueue" :worker-pool-name="workerPoolName" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkerPoolQueue } from '@prefecthq/orion-design'
  import { useRouteParam, useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'

  const api = useWorkspaceApi()
  const workerPoolName = useRouteParam('workerPoolName')
  const workerPoolQueueName = useRouteParam('workerPoolQueueName')
  const subscriptionOptions = {
    interval: 300000,
  }

  const workerPoolQueuesSubscription = useSubscription(api.workerPoolQueues.getWorkerPoolQueueByName, [workerPoolName.value, workerPoolQueueName.value], subscriptionOptions)
  const workerPoolQueue = computed(() => workerPoolQueuesSubscription.response ?? {})
</script>