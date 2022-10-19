<template>
  <p-layout-default class="flows">
    <template #header>
      <PageHeadingFlows />
    </template>

    <template v-if="loaded">
      <template v-if="empty">
        <FlowsPageEmptyState />
      </template>

      <template v-else>
        <FlowsTable />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { FlowsTable, FlowsPageEmptyState, PageHeadingFlows } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { flowsApi } from '@/services/flowsApi'

  const subscriptionOptions = {
    interval: 30000,
  }

  const flowsCountSubscription = useSubscription(flowsApi.getFlowsCount, [{}], subscriptionOptions)
  const flowsCount = computed(() => flowsCountSubscription.response ?? 0)
  const empty = computed(() => flowsCountSubscription.executed && flowsCount.value === 0)
  const loaded = computed(() => flowsCountSubscription.executed)

  usePageTitle('Flows')
</script>
