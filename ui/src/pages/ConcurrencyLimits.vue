<template>
  <p-layout-default class="concurrency-limits">
    <template #header>
      <PageHeading :crumbs="[{ text: 'Task Run Concurrency Limits' }]">
        <template #after-crumbs>
          <p-button inset size="xs" icon="PlusIcon" @click="open" />
        </template>
      </PageHeading>
      <ConcurrencyLimitsCreateModal v-model:showModal="showModal" />
    </template>
    <ConcurrencyLimitsTable />
  </p-layout-default>
</template>

  <script lang="ts" setup>
  import { PageHeading, ConcurrencyLimitsCreateModal, ConcurrencyLimitsTable, useShowModal } from '@prefecthq/prefect-ui-library'

  const { showModal, open } = useShowModal()
</script>
