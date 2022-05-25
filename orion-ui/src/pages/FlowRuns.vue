<template>
  <p-layout-default class="flow-runs">
    <template #header>
      <div class="flow-runs">
        Flow runs
      </div>
    </template>

    <div class="grid gap-1 grid-cols-3">
      <FlowCombobox v-model:selected="flows" empty-message="All flows" />
      <DeploymentCombobox v-model:selected="deployments" empty-message="All deployments" />
      <StateSelect v-model:selected="states" empty-message="All run states" />
    </div>

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
  import { FlowRunList, FlowRunsScatterPlot, StateSelect, StateType, DeploymentCombobox, FlowCombobox } from '@prefecthq/orion-design'
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

  const states = ref<StateType[]>([])
  const deployments = ref<string[]>([])
  const flows = ref<string[]>([])
</script>