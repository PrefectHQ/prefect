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
        <FlowsTable :flows="flows" @delete="flowsSubscription.refresh()" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { Flow, FlowsTable, FlowsPageEmptyState, PageHeadingFlows } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { flowsApi } from '@/services/flowsApi'

  const subscriptionOptions = {
    interval: 30000,
  }

  const flowsSubscription = useSubscription(flowsApi.getFlows, [{}], subscriptionOptions)
  const flows = computed<Flow[]>(() => flowsSubscription.response ?? [])
  const empty = computed(() => flowsSubscription.executed && flows.value.length === 0)
  const loaded = computed(() => flowsSubscription.executed)

  usePageTitle('Flows')
</script>
