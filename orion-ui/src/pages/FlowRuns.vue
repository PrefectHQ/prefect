<template>
  <p-layout-default class="flow-runs">
    <template #header>
      <PageHeadingFlowRuns />
    </template>

    <div class="grid gap-3">
      <div class="grid gap-1">
        <div class="grid gap-1 grid-cols-2">
          <p-label label="Start Date">
            <PDateInput v-model="startDate" />
          </p-label>
          <p-label label="End Date">
            <PDateInput v-model="endDate" />
          </p-label>
        </div>
        <div class="grid gap-1 grid-cols-4">
          <FlowCombobox v-model:selected="flows" empty-message="All flows" />
          <DeploymentCombobox v-model:selected="deployments" empty-message="All deployments" />
          <PTagsInput v-model:tags="tags" empty-message="All Tags" inline />
          <StateSelect v-model:selected="states" empty-message="All run states" />
        </div>
      </div>

      <FlowRunsScatterPlot :history="flowRunHistory" style="height: 275px" />

      <div class="flow-runs--sort-search">
        <FlowRunsSort v-model="sort" />
      </div>

      <FlowRunList :flow-runs="flowRuns" :selected="selectedFlowRuns" disabled />
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingFlowRuns, FlowRunsSort, FlowRunSortValues, FlowRunList, FlowRunsScatterPlot, StateSelect, StateType, DeploymentCombobox, FlowCombobox, useFlowRunFilter } from '@prefecthq/orion-design'
  import { PTagsInput, PDateInput } from '@prefecthq/prefect-design'
  import { useRouteQueryParam, useSubscription } from '@prefecthq/vue-compositions'
  import { endOfWeek, startOfWeek } from 'date-fns'
  import { computed, Ref, ref } from 'vue'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { UiApi } from '@/services/uiApi'

  const sort = ref<FlowRunSortValues>('EXPECTED_START_TIME_DESC')

  const startDateParam = useRouteQueryParam('start-date', startOfWeek(new Date()).toISOString())

  const startDate = computed({
    get() {
      return new Date(startDateParam.value)
    },
    set(value: Date) {
      startDateParam.value = value.toISOString()
    },
  })

  const endDateParam = useRouteQueryParam('end-date', endOfWeek(new Date()).toISOString())

  const endDate = computed({
    get() {
      return new Date(endDateParam.value)
    },
    set(value: Date) {
      endDateParam.value = value.toISOString()
    },
  })

  const states = useRouteQueryParam('state', []) as Ref<StateType[]>
  const deployments = useRouteQueryParam('deployment', [])
  const flows = useRouteQueryParam('flow', [])
  const tags = useRouteQueryParam('tag', [])
  const filter = useFlowRunFilter({ states, deployments, flows, tags, startDate, endDate, sort })

  const subscriptionOptions = {
    interval: 30000,
  }

  const flowRunHistorySubscription = useSubscription(UiApi.getFlowRunHistory, [filter], subscriptionOptions)
  const flowRunHistory = computed(() => flowRunHistorySubscription.response ?? [])

  const flowRunsSubscription = useSubscription(flowRunsApi.getFlowRuns, [filter], subscriptionOptions)
  const flowRuns = computed(()=> flowRunsSubscription.response ?? [])
  const selectedFlowRuns = ref([])
</script>

<style>
.flow-runs--sort-search {
  @apply flex justify-end
}
</style>