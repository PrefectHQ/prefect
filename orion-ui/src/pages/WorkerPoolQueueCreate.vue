<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkerPoolQueueCreate :worker-pool-name="workerPoolName" />
    </template>

    <WorkerPoolQueueCreateForm :worker-pool-name="workerPoolName" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingWorkerPoolQueueCreate, WorkerPoolQueueCreateForm } from '@prefecthq/orion-design'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const workerPoolName = useRouteParam('workerPoolName')

  usePageTitle('Create Worker Pool Queue')
</script>