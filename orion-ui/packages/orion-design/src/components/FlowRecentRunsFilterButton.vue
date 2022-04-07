<template>
  <FilterCountButton :count="recentFlowRunsCount" label="Recent Run" :route="route" :filters="recentFlowRunsFilters" />
</template>


<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { subWeeks, startOfToday } from 'date-fns'
  import { computed } from 'vue'
  import FilterCountButton from '@/components/FilterCountButton.vue'
  import { Flow } from '@/models/Flow'
  import { workspaceDashboardKey } from '@/router/routes'
  import { UnionFilters } from '@/services/Filter'
  import { flowRunsApiKey } from '@/services/FlowRunsApi'
  import { Filter } from '@/types/filters'
  import { inject } from '@/utilities/inject'


  const props = defineProps<{ flow: Flow }>()

  const flowRunsApi = inject(flowRunsApiKey)
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
      operation: 'last',
      value: '1w',
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
      expected_start_time: {
        after_: subWeeks(startOfToday(), 1).toISOString(),
      },
    },
  }))

  const recentFlowRunsCountSubscription = useSubscription(flowRunsApi.getFlowRunsCount, [recentFlowRunsCountFilter])
  const recentFlowRunsCount = computed(() => recentFlowRunsCountSubscription.response ?? 0)
</script>
