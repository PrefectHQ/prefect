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
    <FlowRunsScatterPlot :history="flowRunHistory" style="height: 275px" />

    <div>
      Flow Run List
    </div>
    <FlowRunList :flow-runs="flowRuns" :selected="selectedFlowRuns" disabled />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { FlowRunList, FlowRunsScatterPlot } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { UiApi } from '@/services/uiApi'

  const filter = {}
  const subscriptionOptions = {
    interval: 30000,
  }

  const flowRunHistorySubscription = useSubscription(UiApi.getFlowRunHistory, [filter], subscriptionOptions)
  const flowRunHistory = computed(() => flowRunHistorySubscription.response ?? [])

  const flowRunsSubscription = useSubscription(flowRunsApi.getFlowRuns, [filter], subscriptionOptions)
  const flowRuns = computed(()=> flowRunsSubscription.response ?? [])
  const selectedFlowRuns = ref([])
</script>