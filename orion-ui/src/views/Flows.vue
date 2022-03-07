<template>
  <div class="flows">
    <PageHeader icon="flow">
      Flows
    </PageHeader>

    <m-loader class="flows__loader" :loading="loading" />

    <template v-if="empty">
      <FlowsPageFlowListEmptyState />
    </template>

    <template v-else>
      <div class="flows__controls">
        <m-input v-model="term" placeholder="Search..." />
      </div>
      <FlowsPageFlowList :flows="flows" />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { FlowsPageFlowList, PageHeader, UnionFilters, flowsApi, workspaceDashboardKey, FlowsPageFlowListEmptyState } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, provide, ref } from 'vue'

  // todo: create a routes object with methods like nebula has
  provide(workspaceDashboardKey, {
    name: 'Dashboard',
  })

  const term = ref('')

  const filter = computed<UnionFilters>(() => {
    const filter: UnionFilters = {}

    if (term.value.length > 0) {
      filter.flows = {
        name: {
          any_: [term.value],
        },
      }
    }

    return filter
  })

  const subscriptionOptions = {
    interval: 30000,
  }

  const countFlowsSubscription = useSubscription(flowsApi.getFlowsCount, [{}], subscriptionOptions)
  const flowsSubscription = useSubscription(flowsApi.getFlows, [filter], subscriptionOptions)

  const flows = computed(() => flowsSubscription.response.value ?? [])
  const empty = computed(() => countFlowsSubscription.response.value === 0)
  const loading = computed(() => countFlowsSubscription.response.value === undefined || flowsSubscription.response.value === undefined)
</script>

<style lang="scss" scoped>
.flows {
  position: relative;
}

.flows__loader {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}
.flows__controls {
  display: grid;
  grid-template-columns: 1fr 250px;
  gap: var(--m-1);
  margin-bottom: var(--m-2);
}
</style>