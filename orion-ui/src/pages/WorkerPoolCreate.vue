<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkerPoolCreate />
    </template>

    <WorkerPoolCreateForm />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingWorkerPoolCreate, WorkerPoolCreateForm } from '@prefecthq/orion-design'
  import { usePageTitle } from '@/compositions/usePageTitle'

  usePageTitle('Create Worker Pool')
</script>