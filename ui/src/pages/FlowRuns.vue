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
          <div ref="listControls" class="flow-runs__list-controls" :class="classes.listControls">
            <div class="flow-runs__list-controls--right">
              <ResultsCount v-if="selectedFlowRuns.length == 0" :count="flowRunCount" label="Flow run" />
              <SelectedCount v-else :count="selectedFlowRuns.length" />

              <FlowRunsDeleteButton :selected="selectedFlowRuns" @delete="deleteFlowRuns" />
            </div>

            <p-toggle v-model="parentTaskRunIdNull" class="flow-runs__subflows-toggle" append="Hide subflows" />
            <template v-if="media.md">
              <SearchInput v-model="flowRunNameLike" placeholder="Search by run name" label="Search by run name" />
            </template>
            <FlowRunsSort v-model="filter.sort" class="flow-runs__sort" />
          </div>

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
  import { PageHeadingFlowRuns, FlowRunsPageEmptyState, FlowRunsSort, FlowRunList, FlowRunsScatterPlot, SearchInput, ResultsCount, FlowRunsDeleteButton, FlowRunsFilterGroup, useWorkspaceApi, SelectedCount, useRecentFlowRunsFilterFromRoute, useFlowRunsInfiniteScroll, useOffsetStickyRootMargin } from '@prefecthq/prefect-ui-library'
  import { UsePositionStickyObserverOptions, useDebouncedRef, usePositionStickyObserver, useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'

  const router = useRouter()
  const api = useWorkspaceApi()
  const listControls = ref<HTMLElement>()

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

  const subscriptionOptions = {
    interval: 30000,
  }

  const flowRunCountSubscription = useSubscription(api.flowRuns.getFlowRunsCount, [filter], subscriptionOptions)
  const flowRunCount = computed(() => flowRunCountSubscription.response)

  const flowRunHistorySubscription = useSubscription(api.ui.getFlowRunHistory, [filter], subscriptionOptions)
  const flowRunHistory = computed(() => flowRunHistorySubscription.response ?? [])

  const { flowRuns, subscriptions: flowRunsSubscriptions, loadMore: loadMoreFlowRuns } = useFlowRunsInfiniteScroll(filter, subscriptionOptions)
  const selectedFlowRuns = ref([])

  const { margin } = useOffsetStickyRootMargin()
  const stickyObserverOptions: Getter<UsePositionStickyObserverOptions> = () => ({
    rootMargin: margin.value,
  })
  const { stuck } = usePositionStickyObserver(listControls, stickyObserverOptions)

  const classes = computed(() => ({
    listControls: {
      'flow-runs__list-controls--stuck': stuck.value && media.md,
    },
  }))

  function clear(): void {
    router.push(routes.flowRuns())
  }

  const deleteFlowRuns = (): void => {
    selectedFlowRuns.value = []
    flowRunsSubscriptions.refresh()
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
  flex-wrap
  gap-2
  gap-y-4
  items-center
  py-3
  rounded-b-default
  border-t
  border-t-divider
  md:border-t-0
  md:sticky
  md:top-0
  md:z-10
}

.flow-runs__list-controls--stuck { @apply
  px-2
  bg-floating-sticky
  backdrop-blur-sm
  shadow-md
}

.flow-runs__list-controls--right { @apply
  mr-auto
  flex
  gap-2
  items-center
}

.flow-runs__chart {
  height: 275px;
}

.flow-runs__subflows-toggle { @apply
  mr-2
}

.flow-runs__sort { @apply
  w-full
  md:w-auto
}
</style>