<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkPoolQueueCreate :work-pool-name="workPoolName" />
    </template>

    <WorkPoolQueueCreateForm :work-pool-name="workPoolName" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingWorkPoolQueueCreate, WorkPoolQueueCreateForm } from '@prefecthq/prefect-ui-library'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const workPoolName = useRouteParam('workPoolName')

  usePageTitle('Create Work Pool Queue')
</script>