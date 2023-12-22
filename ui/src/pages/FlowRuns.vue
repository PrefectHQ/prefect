<template>
  <p-layout-default class="flow-runs">
    <template #header>
      <PageHeadingFlowRuns :filter="dashboardFilter" :hide-actions="empty" @update:filter="setDashboardFilter" />
    </template>

    <template v-if="loaded">
      <template v-if="empty">
        <FlowRunsPageEmptyState />
      </template>
      <template v-else>
        <FlowRunsFilterGroup v-model:nameSearch="flowRunNameLike" :filter="dashboardFilter" @update:filter="setDashboardFilter" />

        <template v-if="media.md">
          <FlowRunsScatterPlot
            :history="flowRunHistory"
            :start-date="flowRunsFilter.flowRuns?.expectedStartTimeAfter"
            :end-date="flowRunsFilter.flowRuns?.expectedStartTimeBefore"
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
                <p-toggle v-model="hideSubflows" append="Hide subflows" />
              </div>
              <template v-if="media.md">
                <SearchInput v-model="flowRunNameLike" placeholder="Search by run name" label="Search by run name" />
              </template>
            </template>

            <template #sort>
              <FlowRunsSort v-model="sort" class="flow-runs__sort" />
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
  import { Getter, PEmptyResults, media } from '@prefecthq/prefect-design'
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
    useFlowRuns,
    useWorkspaceFlowRunDashboardFilterFromRoute,
    FlowRunSortValuesSortParam,
    FlowRunsFilter,
    mapper
  } from '@prefecthq/prefect-ui-library'
  import { BooleanRouteParam, useDebouncedRef, useRouteQueryParam, useSubscription } from '@prefecthq/vue-compositions'
  import merge from 'lodash.merge'
  import { computed, ref, toRef } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'

  const router = useRouter()
  const api = useWorkspaceApi()

  const flowRunsCountAllSubscription = useSubscription(api.flowRuns.getFlowRunsCount, [{}])
  const loaded = computed(() => flowRunsCountAllSubscription.executed)
  const empty = computed(() => flowRunsCountAllSubscription.response === 0)

  const { filter: dashboardFilter, setFilter: setDashboardFilter, isCustom: isCustomDashboardFilter } = useWorkspaceFlowRunDashboardFilterFromRoute()

  const flowRunNameLike = ref('')
  const flowRunNameLikeDebounced = useDebouncedRef(flowRunNameLike, 1200)
  const hideSubflows = useRouteQueryParam('hide-subflows', BooleanRouteParam, false)
  const sort = useRouteQueryParam('sort', FlowRunSortValuesSortParam, 'START_TIME_DESC')

  const flowRunsFilter = toRef<Getter<FlowRunsFilter>>(() => {
    const filter = mapper.map('SavedSearchFilter', dashboardFilter, 'FlowRunsFilter')

    return merge({}, filter, {
      flowRuns: {
        nameLike: flowRunNameLikeDebounced.value,
        parentTaskRunIdNull: hideSubflows.value ? true : undefined,
      },
      sort: sort.value,
    })
  })

  const isCustomFilter = computed(() => isCustomDashboardFilter.value || hideSubflows.value || flowRunNameLike.value)

  const interval = 30000


  const flowRunHistorySubscription = useSubscription(api.ui.getFlowRunHistory, [flowRunsFilter], {
    interval,
  })
  const flowRunHistory = computed(() => flowRunHistorySubscription.response ?? [])

  const { flowRuns, total: flowRunCount, subscriptions: flowRunsSubscriptions, next: loadMoreFlowRuns } = useFlowRuns(flowRunsFilter, {
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