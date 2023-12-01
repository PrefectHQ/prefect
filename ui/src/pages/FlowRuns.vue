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
          <FlowRunsScatterPlot
            :history="flowRunHistory"
            :start-date="filter.flowRuns.expectedStartTimeAfter"
            :end-date="filter.flowRuns.expectedStartTimeBefore"
            class="flow-runs__chart"
          />
        </template>

        <div class="flow-runs__list">
          <p-list-header sticky>
            <ResultsCount v-if="selectedFlowRuns.length == 0" :count="flowRunCount" label="Flow run" />
            <SelectedCount v-else :count="selectedFlowRuns.length" />
            <FlowRunsDeleteButton :selected="selectedFlowRuns" @delete="deleteFlowRuns" />

            <template #controls>
              <div class="flow-runs__subflows-toggle">
                <p-toggle v-model="parentTaskRunIdNull" append="Hide subflows" />
              </div>
              <template v-if="media.md">
                <SearchInput v-model="flowRunNameLike" placeholder="Search by run name" label="Search by run name" />
              </template>
            </template>

            <template #sort>
              <FlowRunsSort v-model="filter.sort" class="flow-runs__sort" />
            </template>
          </p-list-header>

          <FlowRunList v-model:selected="selectedFlowRuns" selectable :flow-runs="flowRuns" @bottom="loadMoreFlowRuns" />

          <template v-if="!flowRuns.length">
            <PEmptyResults>
              <template v-if="isCustomFilter" #actions>
                <p-button small @click="clear">
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
  import { PEmptyResults, media } from '@prefecthq/prefect-design'
  import {
    PageHeadingFlowRuns,
    FlowRunsPageEmptyState,
    FlowRunsSort,
    FlowRunList,
    FlowRunsScatterPlot,
    SearchInput,
    ResultsCount,
    FlowRunsDeleteButton,
    FlowRunsFilterGroup,
    useWorkspaceApi,
    SelectedCount,
    useRecentFlowRunsFilterFromRoute,
    useFlowRuns
  } from '@prefecthq/prefect-ui-library'
  import { useDebouncedRef, useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'

  const router = useRouter()
  const api = useWorkspaceApi()

  const flowRunsCountAllSubscription = useSubscription(api.flowRuns.getFlowRunsCount, [{}])
  const loaded = computed(() => flowRunsCountAllSubscription.executed)
  const empty = computed(() => flowRunsCountAllSubscription.response === 0)

  const flowRunNameLike = ref<string>()
  const flowRunNameLikeDebounced = useDebouncedRef(flowRunNameLike, 1200)
  const { filter, isCustomFilter } = useRecentFlowRunsFilterFromRoute({
    flowRuns: {
      nameLike: flowRunNameLikeDebounced,
    },
  })
  const parentTaskRunIdNull = computed({
    get() {
      return filter.flowRuns.parentTaskRunIdNull
    },
    set(val) {
      filter.flowRuns.parentTaskRunIdNull = val ? true : undefined
    },
  })
  const interval = 30000


  const flowRunHistorySubscription = useSubscription(api.ui.getFlowRunHistory, [filter], {
    interval,
  })
  const flowRunHistory = computed(() => flowRunHistorySubscription.response ?? [])

  const { flowRuns, total: flowRunCount, subscriptions: flowRunsSubscriptions, next: loadMoreFlowRuns } = useFlowRuns(filter, {
    mode: 'infinite',
    interval,
  })
  const selectedFlowRuns = ref([])

  function clear(): void {
    router.push(routes.flowRuns())
  }

  const deleteFlowRuns = (): void => {
    selectedFlowRuns.value = []
    flowRunsSubscriptions.refresh()
  }

  usePageTitle('Flow Runs')
</script>

<style>
.flow-runs__list { @apply
  grid
  gap-2
}

.flow-runs__chart {
  height: 275px;
}

.flow-runs__subflows-toggle { @apply
  pr-2
  w-full
  md:w-auto
}
</style>