<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkerPoolQueueEdit :worker-pool-name="workerPoolName" :worker-pool-queue-name="workerPoolQueueName" />
    </template>

    <WorkerPoolQueueEditForm :worker-pool-name="workerPoolName" :worker-pool-queue="workerPoolQueue" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkerPoolQueueEdit, WorkerPoolQueueEditForm } from '@prefecthq/orion-design'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const workerPoolName = useRouteParam('workerPoolName')
  const workerPoolQueueName = useRouteParam('workerPoolQueueName')

  const workerPoolQueue = await api.workerPoolQueues.getWorkerPoolQueueByName(workerPoolName.value, workerPoolQueueName.value)

  usePageTitle('Edit Worker Pool Queue')
</script>