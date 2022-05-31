<template>
  <p-layout-default class="flows">
    <template #header>
      <PageHeadingFlows />
    </template>
    <template v-if="empty">
      <FlowsPageEmptyState />
    </template>
    <template v-else>
      <SearchInput v-model="searchInput" placeholder="Search flows" label="Search by flow name" clearable />
      <FlowsTable :flows="filteredFlowList" @delete="flowsSubscription.refresh()" @clear="clear" />
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { Flow, SearchInput, FlowsTable, FlowsPageEmptyState, PageHeadingFlows } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { flowsApi } from '@/services/flowsApi'

  const filter = {}
  const subscriptionOptions = { interval: 30000 }
  const flowsSubscription = useSubscription(flowsApi.getFlows, [filter], subscriptionOptions)
  const flows = computed<Flow[]>(() => flowsSubscription.response ?? [])
  const empty = computed(() => flowsSubscription.executed && flows.value.length === 0)
  const searchInput = ref('')
  const filteredFlowList = computed(()=> search(flows.value, searchInput.value))

  const search = (array: Flow[], text: string): Flow[] => array.reduce<Flow[]>((previous, current) => {
    if (current.name.toLowerCase().includes(text.toLowerCase())) {
      previous.push(current)
    }

    return previous
  }, [])

  const clear = (): void => {
    searchInput.value = ''
  }
</script>
