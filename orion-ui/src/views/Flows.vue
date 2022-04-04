<template>
  <div class="flows">
    <PageHeader icon="flow" heading="Flows" />

    <m-loader class="flows__loader" :loading="loading" />

    <template v-if="empty">
      <FlowsPageFlowListEmptyState />
    </template>

    <template v-else>
      <div class="flows__controls">
        <m-input v-model="term" placeholder="Search...">
          <template #prepend>
            <i class="pi pi-search-line pi-sm" />
          </template>
        </m-input>
        <TagsInput v-model:tags="tags" />
      </div>
      <FlowsPageFlowList :flows="flows" @bottom="loadMoreFlows" />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import {
    TagsInput,
    FlowsPageFlowList,
    PageHeader,
    UnionFilters,
    workspaceDashboardKey,
    FlowsPageFlowListEmptyState,
    Require,
    useUnionFiltersSubscription
  } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, provide, ref } from 'vue'
  import { flowsApi } from '@/services/flowsApi'

  // todo: create a routes object with methods like nebula has
  provide(workspaceDashboardKey, {
    name: 'Dashboard',
  })

  const term = ref('')
  const tags = ref([])

  const filter = computed<UnionFilters>(() => {
    const filter: Require<UnionFilters, 'flows'> = {
      flows: {},
    }

    if (term.value.length > 0) {
      filter.flows.name = {
        any_: [term.value],
      }
    }

    if (tags.value.length > 0) {
      filter.flows.tags = {
        all_: tags.value,
      }
    }

    return filter
  })

  const subscriptionOptions = {
    interval: 30000,
  }

  const countFlowsSubscription = useSubscription(flowsApi.getFlowsCount, [{}], subscriptionOptions)
  const flowsSubscription = useUnionFiltersSubscription(flowsApi.getFlows, [filter], subscriptionOptions)

  const flows = computed(() => flowsSubscription.response ?? [])
  const empty = computed(() => countFlowsSubscription.response === 0)
  const loading = computed(() => !countFlowsSubscription.executed || !flowsSubscription.executed)

  function loadMoreFlows(): void {
    flowsSubscription.loadMore()
  }
</script>

<style lang="scss" scoped>
@use 'sass:map';

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
  grid-template-columns: 1fr;
  gap: var(--m-2);
  margin-bottom: var(--m-2);

  @media only screen and (min-width: map.get($breakpoints, 'sm')) {
    grid-template-columns: 1fr 250px;
  }
}
</style>