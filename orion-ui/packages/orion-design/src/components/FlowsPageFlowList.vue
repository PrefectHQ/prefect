<template>
  <div class="flows-list">
    <m-card shadow="sm">
      <template v-for="flow in flows" :key="flow.id">
        <FlowsPageFlowListItem :flow="flow" class="flows-list__item" />
      </template>
    </m-card>
    <div v-if="flows.length === 0" class="text-center my-8">
      <h2>No results found</h2>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, inject } from 'vue'
  import FlowsPageFlowListItem from '@/components/FlowsPageFlowListItem.vue'
  import { UnionFilters } from '@/services/Filter'
  import { flowsApi, getFlowsKey } from '@/services/FlowsApi'

  const props = defineProps<{
    filter: UnionFilters,
    interval?: number,
  }>()

  const filter = computed(() => props.filter)
  const getFlows = inject(getFlowsKey, flowsApi.getFlows)

  const flowsSubscription = useSubscription(getFlows, [filter], {
    interval: props.interval,
  })

  console.log({ flowsSubscription })

  const flows = computed(() => flowsSubscription.response.value ?? [])
</script>

<style lang="scss">
.flows-list__item {
  &:not(:first-of-type) {
    border-top: 1px solid var(--secondary-hover);
  }
}
</style>