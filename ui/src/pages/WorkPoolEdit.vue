<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkPoolEdit :work-pool="workPool" />
    </template>

    <WorkPoolEditForm :work-pool="workPool" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkPoolEdit, WorkPoolEditForm } from '@prefecthq/prefect-ui-library'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const workPoolName = useRouteParam('workPoolName')

  const workPool = await api.workPools.getWorkPoolByName(workPoolName.value)


  usePageTitle('Create Work Pool')
</script>