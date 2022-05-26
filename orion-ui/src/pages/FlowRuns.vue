<template>
  <p-layout-default class="flow-runs">
    <template #header>
      <PageHeadingFlowRuns />
    </template>

    <div class="flow-runs__content">
      <div class="flow-runs__filters">
        <div class="flow-runs__date-filters">
          <p-label label="Start Date">
            <PDateInput v-model="startDate" />
          </p-label>
          <p-label label="End Date">
            <PDateInput v-model="endDate" />
          </p-label>
        </div>
        <div class="flow-runs__meta-filters">
          <StateSelect v-model:selected="states" empty-message="All run states" />
          <FlowCombobox v-model:selected="flows" empty-message="All flows" />
          <DeploymentCombobox v-model:selected="deployments" empty-message="All deployments" />
          <PTagsInput v-model:tags="tags" empty-message="All Tags" inline />
        </div>
      </div>

      <FlowRunsScatterPlot :history="flowRunHistory" style="height: 275px" />

      <div class="flow-runs__list">
        <div class="flow-runs__list-controls">
          <ResultsCount :count="flowRunCount" class="mr-auto" />
          <SearchInput v-model="flowRunSearchInput" placeholder="Search by run name" label="Search by run name" />
          <FlowRunsSort v-model="sort" />
        </div>

        <FlowRunList :flow-runs="flowRuns" :selected="selectedFlowRuns" disabled />
      </div>
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingFlowRuns, FlowRunsSort, FlowRunSortValues, FlowRunList, FlowRunsScatterPlot, StateSelect, StateType, DeploymentCombobox, FlowCombobox, useFlowRunFilter, SearchInput, ResultsCount } from '@prefecthq/orion-design'
  import { PTagsInput, PDateInput } from '@prefecthq/prefect-design'
  import { useRouteQueryParam, useSubscription } from '@prefecthq/vue-compositions'
  import { addDays, endOfToday, startOfToday, subDays } from 'date-fns'
  import debounce from 'lodash.debounce'
  import { computed, Ref, ref } from 'vue'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { UiApi } from '@/services/uiApi'

  const sort = ref<FlowRunSortValues>('EXPECTED_START_TIME_DESC')

  const defaultStartDate = subDays(startOfToday(), 7)
  const startDateParam = useRouteQueryParam('start-date', defaultStartDate.toISOString())

  const startDate = computed({
    get() {
      return new Date(startDateParam.value)
    },
    set(value: Date) {
      startDateParam.value = value.toISOString()
    },
  })

  const defaultEndDate = addDays(endOfToday(), 1)
  const endDateParam = useRouteQueryParam('end-date', defaultEndDate.toISOString())

  const endDate = computed({
    get() {
      return new Date(endDateParam.value)
    },
    set(value: Date) {
      endDateParam.value = value.toISOString()
    },
  })

  const flowRunSearchTerm = ref<string>('')
  const flowRunSearchInput = computed({
    get() {
      return flowRunSearchTerm.value ?? null
    },
    set(value: string) {
      updateFlowRunSearchTerm(value)
    },
  })

  const updateFlowRunSearchTerm = debounce((value: string)=> {
    flowRunSearchTerm.value = value
  }, 1200)

  const states = useRouteQueryParam('state', []) as Ref<StateType[]>
  const deployments = useRouteQueryParam('deployment', [])
  const flows = useRouteQueryParam('flow', [])
  const tags = useRouteQueryParam('tag', [])
  const filter = useFlowRunFilter({ states, deployments, flows, tags, startDate, endDate, sort, name: flowRunSearchTerm })

  const subscriptionOptions = {
    interval: 30000,
  }

  const flowRunCountSubscription = useSubscription(flowRunsApi.getFlowRunsCount, [filter], subscriptionOptions)
  const flowRunCount = computed(() => flowRunCountSubscription.response)

  const flowRunHistorySubscription = useSubscription(UiApi.getFlowRunHistory, [filter], subscriptionOptions)
  const flowRunHistory = computed(() => flowRunHistorySubscription.response ?? [])

  const flowRunsSubscription = useSubscription(flowRunsApi.getFlowRuns, [filter], subscriptionOptions)
  const flowRuns = computed(()=> flowRunsSubscription.response ?? [])
  const selectedFlowRuns = ref([])
</script>

<style>
.flow-runs__content { @apply
  grid
  gap-4
}

.flow-runs__filters,
.flow-runs__date-filters,
.flow-runs__meta-filters,
.flow-runs__list { @apply
  grid
  gap-1
}

.flow-runs__date-filters { @apply
  grid-cols-2
}

.flow-runs__meta-filters { @apply
  grid-cols-4
}

.flow-runs__list-controls { @apply
  flex
  gap-1
  items-center
}
</style>