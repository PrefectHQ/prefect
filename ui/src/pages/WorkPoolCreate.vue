<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkPoolCreate />
    </template>

    <WorkPoolCreateForm />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingWorkPoolCreate, WorkPoolCreateForm } from '@prefecthq/prefect-ui-library'
  import { usePageTitle } from '@/compositions/usePageTitle'

  usePageTitle('Create Work Pool')
</script>