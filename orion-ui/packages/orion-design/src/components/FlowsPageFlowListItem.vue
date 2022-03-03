<template>
  <ListItem class="flows-page-flow-list-item">
    <h2 class="flows-page-flow-list-item__name">
      {{ flow.name }}
    </h2>
    <div class="d-flex align-bottom mt-1">
      <div class="font-weight-semibold">
        <i class="pi pi-map-pin-line pi-sm" />
        <span>
          {{ deploymentsCount.toLocaleString() }}
          {{ toPluralString('Deployment', deploymentsCount) }}</span>
      </div>
      <m-tags :tags="flow.tags" class="ml-1" />
    </div>
    <div v-if="media.sm" class="flows-page-flow-list-item__content ml-auto nowrap">
      <FilterButton :route="route" :filters="recentFlowRunsFilters">
        {{ recentFlowRunsCount.toLocaleString() }}
        {{ toPluralString('Recent Run', recentFlowRunsCount) }}
      </FilterButton>
    </div>
  </ListItem>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { subWeeks } from 'date-fns'
  import { computed, inject } from 'vue'
  import FilterButton from '@/components/FilterButton.vue'
  import ListItem from '@/components/ListItem.vue'
  import { Flow } from '@/models/Flow'
  import { workspaceDashboardKey } from '@/router/routes'
  import { deploymentsApi, getDeploymentsCountKey } from '@/services/DeploymentsApi'
  import { UnionFilters } from '@/services/Filter'
  import { flowRunsApi, getFlowRunsCountKey } from '@/services/FlowRunsApi'
  import { Filter } from '@/types/filters'
  import { media } from '@/utilities/media'
  import { toPluralString } from '@/utilities/strings'

  const props = defineProps<{ flow: Flow }>()

  const route = inject(workspaceDashboardKey)

  const recentFlowRunsFilters = computed<Required<Filter>[]>(() => [
    {
      object: 'flow',
      property: 'name',
      type: 'string',
      operation: 'equals',
      value: props.flow.name,
    },
    {
      object: 'flow_run',
      property: 'start_date',
      type: 'date',
      operation: 'newer',
      value: '7d',
    },
  ])

  const countFilter = computed<UnionFilters>(() => ({
    flows: {
      id: {
        any_: [props.flow.id],
      },
    },
  }))

  const recentFlowRunsCountFilter = computed<UnionFilters>(() => ({
    ...countFilter.value,
    flow_runs: {
      start_time: {
        after_: subWeeks(new Date(), 1).toISOString(),
      },
    },
  }))

  const getFlowRunsCount = inject(getFlowRunsCountKey, flowRunsApi.getFlowRunsCount)
  const recentFlowRunsCountSubscription = useSubscription(getFlowRunsCount, [recentFlowRunsCountFilter])
  const recentFlowRunsCount = computed(() => recentFlowRunsCountSubscription.response.value ?? 0)

  const getDeploymentsCount = inject(getDeploymentsCountKey, deploymentsApi.getDeploymentsCount)
  const deploymentsCountSubscription = useSubscription(getDeploymentsCount, [countFilter])
  const deploymentsCount = computed(() => deploymentsCountSubscription.response.value ?? 0)
</script>

<style lang="scss">
.flows-page-flow-list-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.flows-page-flow-list-item__name {
  flex: 1;
  min-width: 0;

  > * {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>