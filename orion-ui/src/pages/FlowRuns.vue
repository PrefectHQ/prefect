<template>
  <p-layout-default class="flow-runs">
    <template #header>
      <div class="flow-runs">
        Flow runs
      </div>
    </template>

    <div>
      Flow Run History
    </div>
    <div v-for="run in flowRunHistory" :key="run.id">
      {{ run }}
    </div>

    <div>
      Flow Run List
    </div>
    <FlowRunsSort v-model="selectedSortOption" />
    <div v-for="flowRun in flowRuns" :key="flowRun.id">
      {{ flowRun }}
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { UnionFilters, FlowRunsSort, FlowRunSortValues } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { UiApi } from '@/services/uiApi'


  const flowRunsOffset = ref<number>(0)
  const flowRunsLimit = ref<number>(1)
  const selectedSortOption = ref<FlowRunSortValues>('EXPECTED_START_TIME_DESC')

  const flowRunsFilter = computed<UnionFilters>(() => {
    return {
      offset: flowRunsOffset.value,
      limit: flowRunsLimit.value,
      sort: selectedSortOption.value,
    }
  })

  const filter = {}
  const subscriptionOptions = {
    interval: 30000,
  }
  const flowRunHistorySubscription = useSubscription(UiApi.getFlowRunHistory, [filter], subscriptionOptions)
  const flowRunHistory = computed(() => flowRunHistorySubscription.response ?? [])

  const flowRunsSubscription = useSubscription(flowRunsApi.getFlowRuns, [flowRunsFilter], subscriptionOptions)
  const flowRuns = computed(()=> flowRunsSubscription.response ?? [])
</script>