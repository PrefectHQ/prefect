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

  const sort = ref<'STATE_ASC' | 'STATE_DESC'>('STATE_ASC')

  const filter = computed<UnionFilters>(() => ({
    sort: sort.value,
  }))

  const flowsSubscription = useSubscription(flowsApi.getFlows, [filter], {
    interval: 30000,
  })

  const flows = computed(() => flowsSubscription.response.value ?? [])
  const empty = computed(() => flowsSubscription.response.value !== undefined && flows.value.length === 0)
  const loading = computed(() => flowsSubscription.response.value === undefined)
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
</style>