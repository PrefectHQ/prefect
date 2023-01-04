<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkerPoolEdit :worker-pool="workerPool" />
    </template>

    <WorkerPoolEditForm :worker-pool="workerPool" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkerPoolEdit, WorkerPoolEditForm } from '@prefecthq/orion-design'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const workerPoolName = useRouteParam('workerPoolName')

  const workerPool = await api.workerPools.getWorkerPoolByName(workerPoolName.value)


  usePageTitle('Create Worker Pool')
</script>