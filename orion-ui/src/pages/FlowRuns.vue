<template>
  <p-layout-default class="flow-runs">
    <template #header>
      <PageHeadingFlowRuns />
    </template>

    <template v-if="loaded">
      <template v-if="empty">
        <FlowRunsPageEmptyState />
      </template>
      <template v-else>
        <FlowRunsFilterGroup />

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
            <DeleteFlowRunsButton :selected="selectedFlowRuns" @delete="deleteFlowRuns" />
          </div>

          <FlowRunList v-model:selected="selectedFlowRuns" :flow-runs="flowRuns" />

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
  import { PageHeadingFlowRuns, FlowRunsPageEmptyState, FlowRunsSort, FlowRunList, FlowRunsScatterPlot, SearchInput, ResultsCount, useFlowRunFilterFromRoute, DeleteFlowRunsButton, FlowRunsFilterGroup, useWorkspaceApi } from '@prefecthq/orion-design'
  import { PEmptyResults, media } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'
  import { uiApi } from '@/services/uiApi'

  const router = useRouter()
  const api = useWorkspaceApi()

  const flowRunsCountAllSubscription = useSubscription(api.flowRuns.getFlowRunsCount, [{}])
  const loaded = computed(() => flowRunsCountAllSubscription.executed)
  const empty = computed(() => flowRunsCountAllSubscription.response === 0)

  const { filter, hasFilters, startDate, endDate, name, sort } = useFlowRunFilterFromRoute()

  const subscriptionOptions = {
    interval: 30000,
  }

  const flowRunCountSubscription = useSubscription(api.flowRuns.getFlowRunsCount, [filter], subscriptionOptions)
  const flowRunCount = computed(() => flowRunCountSubscription.response)

  const flowRunHistorySubscription = useSubscription(uiApi.getFlowRunHistory, [filter], subscriptionOptions)
  const flowRunHistory = computed(() => flowRunHistorySubscription.response ?? [])

  const flowRunsSubscription = useSubscription(api.flowRuns.getFlowRuns, [filter], subscriptionOptions)
  const flowRuns = computed(() => flowRunsSubscription.response ?? [])
  const selectedFlowRuns = ref([])

  function clear(): void {
    router.push(routes.flowRuns())
  }

  const deleteFlowRuns = (): void => {
    selectedFlowRuns.value = []
    flowRunsSubscription.refresh()
    flowRunCountSubscription.refresh()
  }

  usePageTitle('Flow Runs')
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