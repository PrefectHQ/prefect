<template>
  <p-layout-default class="concurrency-limits">
    <template #header>
      <PageHeading :crumbs="[{ text: 'Concurrency' }]" />
    </template>
    <p-tabs v-model:selected="tab" :tabs="tabs">
      <template #global>
        <PageHeading size="lg" :crumbs="[{ text: 'Global Concurrency Limits' }]">
          <template #after-crumbs>
            <p-button small icon="PlusIcon" @click="openGlobal" />
          </template>
        </PageHeading>
        <ConcurrencyLimitsV2CreateModal v-model:showModal="showModalGlobal" />
        <ConcurrencyLimitsV2Table />
      </template>
      <template #task-run>
        <PageHeading size="lg" :crumbs="[{ text: 'Task Run Concurrency Limits' }]">
          <template #after-crumbs>
            <p-button small icon="PlusIcon" @click="openTaskRun" />
          </template>
        </PageHeading>
        <ConcurrencyLimitsCreateModal v-model:showModal="showModalTaskRun" />
        <ConcurrencyLimitsTable class="concurrency-limits__task-limits-table" />
      </template>
    </p-tabs>
  </p-layout-default>
</template>

  <script lang="ts" setup>
  import { PageHeading, ConcurrencyLimitsV2Table, ConcurrencyLimitsTable, ConcurrencyLimitsCreateModal, ConcurrencyLimitsV2CreateModal, useShowModal, useTabs } from '@prefecthq/prefect-ui-library'
  import { computed } from 'vue'
  
  const { showModal: showModalGlobal, open: openGlobal } = useShowModal()
  const { showModal: showModalTaskRun, open: openTaskRun } = useShowModal()

  const computedTabs = computed(() => [
    { label: 'Global' },
    { label: 'Task Run' },
  ])

  const { tab, tabs } = useTabs(computedTabs)

</script>

<style>
.concurrency-limits__event-feed { @apply
  mb-2
  mt-4
}

.concurrency-limits__task-limits-table { @apply
  mb-2
  mt-4
}
</style>