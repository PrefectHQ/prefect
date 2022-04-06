<template>
  <FilterCountButton class="mr-1" :filters="filterByFlowName" :count="flowRunCount" label="Flow Run" />
</template>


<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, inject } from 'vue'
  import FilterCountButton from '@/components/FilterCountButton.vue'
  import { useFilterQuery } from '@/compositions/useFilterQuery'
  import { Flow } from '@/models/Flow'
  import { UnionFilters } from '@/services/Filter'
  import { flowRunsApiKey } from '@/services/FlowRunsApi'
  import { useFiltersStore } from '@/stores/filters'
  import { Filter } from '@/types/filters'

  const props = defineProps<{ flow: Flow }>()

  const filtersStore = useFiltersStore()
  const filter = useFilterQuery()

  const filterByFlowName = computed<Required<Filter>[]>(() => [
    ...filtersStore.all,
    {
      object: 'flow',
      property: 'name',
      type: 'string',
      operation: 'equals',
      value: props.flow.name,
    },
  ])

  const countFilter = computed<UnionFilters>(() => ({
    ...filter.value,
    flows: {
      id: {
        any_: [props.flow.id],
      },
    },
  }))

  const flowRunsApi = inject(flowRunsApiKey)!
  const flowRunCountSubscription = useSubscription(flowRunsApi.getFlowRunsCount, [countFilter])
  const flowRunCount = computed(() => flowRunCountSubscription.response ?? 0)
</script>
