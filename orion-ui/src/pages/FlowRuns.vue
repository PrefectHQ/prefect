<template>
  <p-layout-default class="flow-runs">
    <template #header>
      <div>
        Flow runs
      </div>
    </template>

    <div>
      Flow Run History
    </div>
    <FlowRunsScatterPlot :history="flowRunHistory" style="height: 275px" />

    <div>
      Flow Run List
    </div>
    <div class="flow-runs--sort-search">
      <FlowRunsSearch v-model="flowRunSearchInput" />
      <FlowRunsSort v-model="selectedSortOption" />
    </div>

    <FlowRunList :flow-runs="flowRuns" :selected="selectedFlowRuns" disabled />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { UnionFilters, FlowRunsSort, FlowRunSortValues, FlowRunList, FlowRunsScatterPlot } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { UiApi } from '@/services/uiApi'


  const flowRunsOffset = ref<number>(0)
  const flowRunsLimit = ref<number>(100)
  const flowRunSearchInput = ref(null)
  const selectedSortOption = ref<FlowRunSortValues>('EXPECTED_START_TIME_DESC')

  const flowRunsFilter = computed<UnionFilters>(() => {
    const runFilter = {
      offset: flowRunsOffset.value,
      limit: flowRunsLimit.value,
      sort: selectedSortOption.value,
    }
    if (flowRunSearchInput.value) {
      runFilter.flow_runs =  {
        name: {
          any_: [flowRunSearchInput.value],
        },
      }
    }
    return  runFilter
  })


  const filter = {}
  const subscriptionOptions = {
    interval: 30000,
  }

  const flowRunHistorySubscription = useSubscription(UiApi.getFlowRunHistory, [filter], subscriptionOptions)
  const flowRunHistory = computed(() => flowRunHistorySubscription.response ?? [])

  const flowRunsSubscription = useSubscription(flowRunsApi.getFlowRuns, [flowRunsFilter], subscriptionOptions)
  const flowRuns = computed(()=> flowRunsSubscription.response ?? [])
  const selectedFlowRuns = ref([])
</script>

<style>
.flow-runs--sort-search {
  @apply flex justify-end
}
</style>