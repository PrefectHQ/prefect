<template>
  <p-layout-default class="flow-runs">
    <template #header>
      <PageHeadingFlowRuns v-model:selected="selectedFilterType" />
    </template>

    <template v-if="loaded">
      <template v-if="empty">
        <FlowRunsPageEmptyState />
      </template>
      <template v-else>
        <FlowRunsFilter />

        <template v-if="media.md">
          <FlowRunsScatterPlot :history="flowRunHistory" v-bind="{ startDate, endDate }" class="flow-runs__chart" />
        </template>

        <div class="flow-runs__list">
          <div class="flow-runs__list-controls">
            <ResultsCount :count="flowRunCount" class="mr-auto" />
            <template v-if="media.md">
              <SearchInput v-model="name" placeholder="Search by run name" label="Search by run name" />
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
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { PageHeadingFlowRuns, FlowRunsPageEmptyState, FlowRunsSort, FlowRunList, FlowRunsScatterPlot, SearchInput, ResultsCount, useFlowRunFilterFromRoute, stateType } from '@prefecthq/orion-design'
  import { PEmptyResults, media, formatDateTimeNumeric } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { startOfToday, subDays } from 'date-fns'
  import { computed, ref, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import FlowRunsFilter from '@/components/FlowRunsFilter.vue'
  import { routes } from '@/router'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { uiApi } from '@/services/uiApi'

  const router = useRouter()

  const flowRunsCountAllSubscription = useSubscription(flowRunsApi.getFlowRunsCount, [{}])
  const loaded = computed(() => flowRunsCountAllSubscription.executed)
  const empty = computed(() => flowRunsCountAllSubscription.response === 0)

  const { filter, hasFilters, startDate, endDate, name, sort, states } = useFlowRunFilterFromRoute()

  const selectedFilterType = ref('week')

  watch(selectedFilterType, async ()=> {
    await router.push(routes.flowRuns())
    if (selectedFilterType.value === 'noScheduled') {
      states.value = stateType.filter(state => state !== 'scheduled')
      startDate.value = formatDateTimeNumeric(subDays(startOfToday(), 7))
      return
    } if (selectedFilterType.value === 'day') {
      startDate.value = formatDateTimeNumeric(subDays(startOfToday(), 1))
      states.value = []
      return
    } if (selectedFilterType.value === 'day') {
      states.value = []
      startDate.value = formatDateTimeNumeric(subDays(startOfToday(), 7))
    }
  })

  const subscriptionOptions = {
    interval: 30000,
  }


  const flowRunCountSubscription = useSubscription(flowRunsApi.getFlowRunsCount, [filter], subscriptionOptions)
  const flowRunCount = computed(() => flowRunCountSubscription.response)

  const flowRunHistorySubscription = useSubscription(uiApi.getFlowRunHistory, [filter], subscriptionOptions)
  const flowRunHistory = computed(() => flowRunHistorySubscription.response ?? [])

  const flowRunsSubscription = useSubscription(flowRunsApi.getFlowRuns, [filter], subscriptionOptions)
  const flowRuns = computed(() => flowRunsSubscription.response ?? [])
  const selectedFlowRuns = ref([])

  function clear(): void {
    selectedFilterType.value = 'week'
  }
</script>

<style>
.flow-runs__list { @apply
  grid
  gap-2
}

.flow-runs__list-controls { @apply
  flex
  gap-2
  items-center
}

.flow-runs__chart {
  height: 275px;
}
</style>