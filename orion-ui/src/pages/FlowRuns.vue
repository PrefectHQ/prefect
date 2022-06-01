<template>
  <p-layout-default class="flow-runs">
    <template #header>
      <PageHeadingFlowRuns />
    </template>

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
        <template v-if="!media.md">
          <SearchInput v-model="flowRunSearchInput" placeholder="Search by run name" label="Search by run name" />
        </template>
      </div>
    </div>

    <template v-if="media.md">
      <FlowRunsScatterPlot :history="flowRunHistory" style="height: 275px" />
    </template>

    <div class="flow-runs__list">
      <div class="flow-runs__list-controls">
        <ResultsCount :count="flowRunCount" class="mr-auto" />
        <template v-if="media.md">
          <SearchInput v-model="flowRunSearchInput" placeholder="Search by run name" label="Search by run name" />
        </template>
        <FlowRunsSort v-model="sort" />
      </div>

      <FlowRunList :flow-runs="flowRuns" :selected="selectedFlowRuns" disabled />
      <template v-if="!flowRuns.length">
        <PEmptyResults>
          <template v-if="hasFilters" #actions>
            <p-button size="sm" secondary @click="clear">
              Clear Filters
            </p-button>
          </template>
        </PEmptyResults>
      </template>
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingFlowRuns, FlowRunsSort, FlowRunSortValues, FlowRunList, FlowRunsScatterPlot, StateSelect, StateType, DeploymentCombobox, FlowCombobox, useFlowRunFilter, SearchInput, ResultsCount } from '@prefecthq/orion-design'
  import { PTagsInput, PDateInput, PEmptyResults, formatDateTimeNumeric, parseDateTimeNumeric, media } from '@prefecthq/prefect-design'
  import { useRouteQueryParam, useSubscription } from '@prefecthq/vue-compositions'
  import { addDays, endOfToday, startOfToday, subDays } from 'date-fns'
  import debounce from 'lodash.debounce'
  import { computed, Ref, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { UiApi } from '@/services/uiApi'

  const router = useRouter()
  const sort = ref<FlowRunSortValues>('EXPECTED_START_TIME_DESC')

  const defaultStartDate = formatDateTimeNumeric(subDays(startOfToday(), 7))
  const startDateParam = useRouteQueryParam('start-date', defaultStartDate)

  const startDate = computed({
    get() {
      return parseDateTimeNumeric(startDateParam.value)
    },
    set(value: Date) {
      startDateParam.value = formatDateTimeNumeric(value)
    },
  })

  const defaultEndDate = formatDateTimeNumeric(addDays(endOfToday(), 1))
  const endDateParam = useRouteQueryParam('end-date', defaultEndDate)

  const endDate = computed({
    get() {
      return parseDateTimeNumeric(endDateParam.value)
    },
    set(value: Date) {
      endDateParam.value = formatDateTimeNumeric(value)
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

  const hasFilters = computed(() => {
    return states.value.length ||
      deployments.value.length ||
      flows.value.length ||
      tags.value.length ||
      startDateParam.value !== defaultStartDate ||
      endDateParam.value !== defaultEndDate
  })

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

  function clear(): void {
    router.push(routes.flowRuns())
  }
</script>

<style>
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
  grid-cols-1
}

.flow-runs__list-controls { @apply
  flex
  gap-1
  items-center
}

@screen md {
  .flow-runs__meta-filters { @apply
    grid-cols-4
  }
}
</style>