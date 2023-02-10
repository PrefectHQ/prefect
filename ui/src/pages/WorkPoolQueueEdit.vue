<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkPoolQueueEdit :work-pool-name="workPoolName" :work-pool-queue-name="workPoolQueueName" />
    </template>

    <WorkPoolQueueEditForm :work-pool-name="workPoolName" :work-pool-queue="workPoolQueue" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkPoolQueueEdit, WorkPoolQueueEditForm } from '@prefecthq/prefect-ui-library'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const workPoolName = useRouteParam('workPoolName')
  const workPoolQueueName = useRouteParam('workPoolQueueName')

  const workPoolQueue = await api.workPoolQueues.getWorkPoolQueueByName(workPoolName.value, workPoolQueueName.value)

  usePageTitle('Edit Work Pool Queue')
</script>