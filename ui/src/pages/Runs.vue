<template>
  <p-layout-default class="runs">
    <template #header>
      <PageHeadingRuns :filter="dashboardFilter" :hide-actions="empty" @update:filter="setDashboardFilter" />
    </template>

    <template v-if="loaded">
      <template v-if="empty">
        <FlowRunsPageEmptyState />
      </template>
      <template v-else>
        <p-content>
          <FlowRunsFilterGroup v-model:nameSearch="flowRunNameLike" :filter="dashboardFilter" @update:filter="setDashboardFilter" />

          <p-tabs-root v-model="tab" :default-value="tabs[0]">
            <p-tabs-list>
              <p-tabs-trigger value="flow-runs">
                Flow runs
              </p-tabs-trigger>
              <p-tabs-trigger value="task-runs">
                Task runs
              </p-tabs-trigger>
            </p-tabs-list>
            <p-tabs-content value="flow-runs">
              <p-content>
                <template v-if="media.md">
                  <p-card>
                    <FlowRunsScatterPlot
                      :history="flowRunHistory"
                      :start-date="flowRunsFilterRef.flowRuns?.expectedStartTimeAfter"
                      :end-date="flowRunsFilterRef.flowRuns?.expectedStartTimeBefore"
                      class="runs__scatter-plot"
                    />
                  </p-card>
                </template>

                <p-list-header class="min-h-10" sticky>
                  <p-select-all-checkbox v-if="flowRunsAreSelectable" v-model="selectedFlowRuns" :selectable="flowRuns.map(flowRun => flowRun.id)" item-name="flow run" />
                  <ResultsCount v-if="selectedFlowRuns.length == 0" :count="flowRunCount" label="run" />
                  <SelectedCount v-else :count="selectedFlowRuns.length" />
                  <FlowRunsDeleteButton v-if="can.delete.flow_run" :selected="selectedFlowRuns" @delete="deleteFlowRuns" />

                  <template #controls>
                    <div class="runs__subflows-toggle">
                      <p-toggle v-model="hideSubflows" append="Hide subflows" />
                    </div>
                    <template v-if="media.md">
                      <SearchInput v-model="flowRunNameLike" size="small" placeholder="Search by flow run name" class="min-w-64" label="Search by flow run name" />
                    </template>
                  </template>

                  <template #sort>
                    <FlowRunsSort v-model="flowRunsSort" small />
                  </template>
                </p-list-header>

                <p-pager v-model:limit="limit" v-model:page="flowRunsPage" :pages="flowRunPages" />

                <template v-if="flowRunCount > 0">
                  <FlowRunList v-model:selected="selectedFlowRuns" :selectable="flowRunsAreSelectable" :flow-runs />
                </template>

                <template v-else-if="!flowRunsSubscription.executed && flowRunsSubscription.loading">
                  <p-loading-icon class="m-auto" />
                </template>

                <template v-else-if="!flowRunsSubscription.executed">
                  <p-message type="error">
                    An error occurred while loading flow runs. Please try again.
                  </p-message>
                </template>

                <template v-else>
                  <p-empty-results>
                    <template #message>
                      No flow runs
                    </template>
                    <template v-if="isCustomFilter" #actions>
                      <p-button size="sm" @click="clear">
                        Clear Filters
                      </p-button>
                    </template>
                  </p-empty-results>
                </template>
              </p-content>
            </p-tabs-content>
            <p-tabs-content value="task-runs">
              <p-content>
                <p-list-header class="min-h-10" sticky>
                  <p-select-all-checkbox v-if="taskRunsAreSelectable" v-model="selectedTaskRuns" :selectable="taskRuns.map(taskRun => taskRun.id)" item-name="task run" />
                  <ResultsCount v-if="selectedTaskRuns.length == 0" :count="taskRunCount" label="run" />
                  <SelectedCount v-else :count="selectedTaskRuns.length" />
                  <TaskRunsDeleteButton v-if="can.delete.task_run" :selected="selectedTaskRuns" @delete="deleteTaskRuns" />

                  <template #controls>
                    <template v-if="media.md">
                      <SearchInput v-model="taskRunNameLike" size="small" placeholder="Search by task run name" class="min-w-64" label="Search by task run name" />
                    </template>
                  </template>

                  <template #sort>
                    <TaskRunsSort v-model="taskRunsSort" small />
                  </template>
                </p-list-header>

                <template v-if="taskRunCount > 0">
                  <p-pager v-model:limit="limit" v-model:page="taskRunsPage" :pages="taskRunsPages" />
                  <TaskRunList v-model:selected="selectedTaskRuns" :selectable="taskRunsAreSelectable" :task-runs="taskRuns" />
                </template>

                <template v-else-if="!taskRunsSubscriptions.executed && taskRunsSubscriptions.loading">
                  <p-loading-icon class="m-auto" />
                </template>

                <template v-else-if="!taskRunsSubscriptions.executed">
                  <p-message type="error">
                    An error occurred while loading task runs. Please try again.
                  </p-message>
                </template>

                <template v-else>
                  <p-empty-results>
                    <template #message>
                      No task runs
                    </template>
                    <template v-if="isCustomFilter" #actions>
                      <p-button size="sm" @click="clear">
                        Clear Filters
                      </p-button>
                    </template>
                  </p-empty-results>
                </template>
              </p-content>
            </p-tabs-content>
          </p-tabs-root>
        </p-content>
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { Getter, media } from '@prefecthq/prefect-design'
  import {
    PageHeadingRuns,
    FlowRunsPageEmptyState,
    FlowRunsSort,
    FlowRunList,
    TaskRunList,
    FlowRunsScatterPlot,
    SearchInput,
    ResultsCount,
    FlowRunsFilterGroup,
    TaskRunsDeleteButton,
    useWorkspaceApi,
    SelectedCount,
    FlowRunsDeleteButton,
    usePaginatedTaskRuns,
    usePaginatedFlowRuns,
    useWorkspaceFlowRunDashboardFilterFromRoute,
    FlowRunsFilter,
    FlowRunSortValuesSortParam,
    TaskRunsFilter,
    TaskRunSortValuesSortParam,
    TaskRunsSort,
    FlowRunsPaginationFilter
  } from '@prefecthq/prefect-ui-library'
  import { BooleanRouteParam, NullableStringRouteParam, NumberRouteParam, useDebouncedRef, useLocalStorage, useRouteQueryParam, useSubscription } from '@prefecthq/vue-compositions'
  import merge from 'lodash.merge'
  import { computed, ref, toRef } from 'vue'
  import { useRouter } from 'vue-router'
  import { useCan } from '@/compositions/useCan'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router/routes'
  import { mapper } from '@/services/mapper'

  const api = useWorkspaceApi()
  const router = useRouter()
  const can = useCan()

  const tab = useRouteQueryParam('tab', 'flow-runs')
  const tabs = ['flow-runs', 'task-runs']

  const flowRunsCountAllSubscription = useSubscription(api.flowRuns.getFlowRunsCount)
  const taskRunsCountAllSubscription = useSubscription(api.taskRuns.getTaskRunsCount)

  const loaded = computed(() => flowRunsCountAllSubscription.executed && taskRunsCountAllSubscription.executed)
  const empty = computed(() => flowRunsCountAllSubscription.response === 0 && taskRunsCountAllSubscription.response === 0)

  const { filter: dashboardFilter, setFilter: setDashboardFilter, isCustom: isCustomDashboardFilter } = useWorkspaceFlowRunDashboardFilterFromRoute()

  const flowRunNameLike = useRouteQueryParam('flow-run-search', NullableStringRouteParam, null)
  const flowRunNameLikeDebounced = useDebouncedRef(flowRunNameLike, 1200)

  const taskRunNameLike = useRouteQueryParam('task-run-search', NullableStringRouteParam, null)
  const taskRunNameLikeDebounced = useDebouncedRef(taskRunNameLike, 1200)

  const hideSubflows = useRouteQueryParam('hide-subflows', BooleanRouteParam, false)
  const flowRunsSort = useRouteQueryParam('flow-runs-sort', FlowRunSortValuesSortParam, 'START_TIME_DESC')
  const taskRunsSort = useRouteQueryParam('task-runs-sort', TaskRunSortValuesSortParam, 'EXPECTED_START_TIME_DESC')
  const flowRunsPage = useRouteQueryParam('flow-runs-page', NumberRouteParam, 1)

  const { value: limit } = useLocalStorage('workspace-runs-list-limit', 100)

  const flowRunsFilter: Getter<FlowRunsPaginationFilter> = () => {
    const filter = mapper.map('SavedSearchFilter', dashboardFilter, 'FlowRunsFilter')

    return merge({}, filter, {
      flowRuns: {
        nameLike: flowRunNameLikeDebounced.value ?? undefined,
        parentTaskRunIdNull: hideSubflows.value ? true : undefined,
      },
      sort: flowRunsSort.value,
      limit: limit.value,
      page: flowRunsPage.value,
    })
  }

  const flowRunsFilterRef = toRef(flowRunsFilter)

  const taskRunsPage = useRouteQueryParam('task-runs-page', NumberRouteParam, 1)

  const taskRunsFilter = toRef<Getter<TaskRunsFilter>>(() => {
    const filter = mapper.map('SavedSearchFilter', dashboardFilter, 'TaskRunsFilter')

    return merge({}, filter, {
      taskRuns: {
        nameLike: taskRunNameLikeDebounced.value,
      },
      sort: taskRunsSort.value,
      limit: limit.value,
      page: taskRunsPage.value,
    })
  })

  const isCustomFilter = computed(() => isCustomDashboardFilter.value || hideSubflows.value || flowRunNameLike.value)

  const interval = 30000

  const flowRunsHistoryFilter: Getter<FlowRunsFilter> = () => {
    const filter = mapper.map('SavedSearchFilter', dashboardFilter, 'FlowRunsFilter')

    return merge({}, filter, {
      flowRuns: {
        nameLike: flowRunNameLikeDebounced.value ?? undefined,
        parentTaskRunIdNull: hideSubflows.value ? true : undefined,
      },
      sort: flowRunsSort.value,
      limit: limit.value,
      offset: (flowRunsPage.value - 1) * limit.value,
    })
  }

  const flowRunsHistoryFilterRef = toRef(flowRunsHistoryFilter)

  const flowRunHistorySubscription = useSubscription(api.ui.getFlowRunHistory, [flowRunsHistoryFilterRef], {
    interval,
  })

  const flowRunHistory = computed(() => flowRunHistorySubscription.response ?? [])

  const { flowRuns, count: flowRunCount, pages: flowRunPages, subscription: flowRunsSubscription } = usePaginatedFlowRuns(flowRunsFilter, {
    interval,
  })

  const { taskRuns, count: taskRunCount, subscription: taskRunsSubscriptions, pages: taskRunsPages } = usePaginatedTaskRuns(taskRunsFilter, {
    interval,
  })

  const flowRunsAreSelectable = computed(() => can.delete.flow_run)
  const selectedFlowRuns = ref([])

  const taskRunsAreSelectable = computed(() => can.delete.task_run)
  const selectedTaskRuns = ref([])

  function clear(): void {
    router.push(routes.runs({ tab: tab.value }))
  }

  usePageTitle('Runs')

  const deleteFlowRuns = (): void => {
    selectedFlowRuns.value = []
    flowRunsSubscription.refresh()
  }

  const deleteTaskRuns = (): void => {
    selectedTaskRuns.value = []
    taskRunsSubscriptions.refresh()
  }
</script>

<style>
.runs__scatter-plot {
  height: 275px !important;
}

.runs__chameleon-link { @apply
  text-link
  font-semibold
  cursor-pointer
  hover:underline
}

.runs__subflows-toggle { @apply
  pr-2
  w-full
  md:w-auto
}
</style>
