<template>
  <p-layout-well class="flow-run">
    <template #header>
      <PageHeadingFlowRun v-if="flowRun" :flow-run="flowRun" @delete="goToFlowRuns">
        <div class="flow-run__header-meta">
          <StateBadge :state="flowRun.state" />
          <DurationIconText :duration="flowRun.duration" />
          <FlowIconText :flow-id="flowRun.flowId" />
        </div>
      </PageHeadingFlowRun>
    </template>

    <p-tabs :tabs="tabs">
      <template #details>
        <FlowRunDetails v-if="flowRun" :flow-run="flowRun" />
      </template>

      <template #logs>
        <div class="flow-run__filters">
          <LogLevelSelect v-model:selected="logLevel" />
        </div>
        <LogsContainer :logs="logs" class="flow-run__logs" />
      </template>

      <template #task-runs>
        <div class="flow-run__filters">
          <StateSelect v-model:selected="state" empty-message="All states" class="mr-auto" />
          <SearchInput v-model="taskRunSearch" placeholder="Search by run name" label="Search by run name" />
          <TaskRunsSort v-model="selectedTaskRunSortOption" />
        </div>

        <TaskRunList :selected="[]" :task-runs="taskRuns" disabled @bottom="taskRunsSubscription.loadMore" />
      </template>

      <template #sub-flow-runs>
        <div class="flow-run__filters">
          <StateSelect v-model:selected="state" empty-message="All states" class="mr-auto" />
          <SearchInput v-model="taskRunSearch" placeholder="Search by run name" label="Search by run name" />
          <FlowRunsSort v-model="selectedSubFlowRunSortOption" />
        </div>

        <FlowRunList :flow-runs="subFlowRuns" :selected="selectedSubFlowRuns" disabled @bottom="loadMoreSubFlowRuns" />
      </template>
    </p-tabs>

    <template #well>
      <template v-if="flowRun">
        <div class="flow-run__meta">
          <StateBadge :state="flowRun.state" />
          <DurationIconText :duration="flowRun.duration" />
          <FlowIconText :flow-id="flowRun.flowId" />
          <DeploymentIconText v-if="flowRun.deploymentId" :deployment-id="flowRun.deploymentId" />
        </div>
        <PDivider />

        <router-link :to="routes.radar(flowRunId)" class="flow-run__small-radar-link">
          <RadarSmall :flow-run-id="flowRunId" class="flow-run__small-radar" />
        </router-link>
        <PDivider />
        <FlowRunDetails :flow-run="flowRun" />
      </template>
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import {
    useRouteParam,
    Log,
    LogsRequestFilter,
    TaskRun,
    UnionFilters,
    LogsRequestSort,
    FlowRunList,
    useUnionFiltersSubscription,
    TaskRunsSort,
    TaskRunSortValues,
    FlowRunsSort,
    SearchInput,
    PageHeadingFlowRun,
    LogsContainer,
    TaskRunList,
    FlowRunDetails,
    RadarSmall,
    StateSelect,
    StateType,
    StateBadge,
    FlowIconText,
    DeploymentIconText,
    DurationIconText,
    LogLevelSelect,
    LogLevel
  } from '@prefecthq/orion-design'
  import { PDivider, media } from '@prefecthq/prefect-design'
  import { useDebouncedRef, useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { logsApi } from '@/services/logsApi'
  import { taskRunsApi } from '@/services/taskRunsApi'

  const router = useRouter()
  const flowRunId = useRouteParam('id')

  const tabs = computed(() => {
    const values = ['Logs', 'Task Runs', 'Sub Flow Runs']

    if (!media.xl) {
      values.push('Details')
    }

    return values
  })
  const options = { interval:  5000 }

  const flowRunDetailsSubscription = useSubscription(flowRunsApi.getFlowRun, [flowRunId.value], options)
  const flowRun = computed(()=> flowRunDetailsSubscription.response)

  const state = ref<StateType>()
  const logLevel = ref<LogLevel>(0)
  const logsOffset = ref<number>(0)
  const logsSort = ref<LogsRequestSort>('TIMESTAMP_DESC')
  const logsFilter = computed<LogsRequestFilter>(() => ({
    logs: {
      flow_run_id: {
        any_: [flowRunId.value],
      },
      level: {
        ge_: logLevel.value,
      },
    },
    offset: logsOffset.value,
    sort: logsSort.value,
  }))

  const logsSubscription = useSubscription(logsApi.getLogs, [logsFilter], options)
  const logs = computed<Log[]>(() => logsSubscription.response ?? [])

  const selectedTaskRunSortOption = ref<TaskRunSortValues>('EXPECTED_START_TIME_DESC')
  const taskRunSearch = ref('')
  const taskRunSearchDebounced = useDebouncedRef(taskRunSearch, 1200)

  const taskRunsFilter = computed<UnionFilters>(() => {
    const runFilter: UnionFilters = {
      flow_runs: {
        id: {
          any_: [flowRunId.value],
        },
      },
      sort: selectedTaskRunSortOption.value,
    }
    if (taskRunSearchDebounced.value) {
      runFilter.task_runs =  {
        name: {
          any_: [taskRunSearchDebounced.value],
        },
      }
    }
    return  runFilter
  })

  const taskRunsSubscription = useUnionFiltersSubscription(taskRunsApi.getTaskRuns, [taskRunsFilter], options)
  const taskRuns = computed<TaskRun[]>(() => taskRunsSubscription.response ?? [])

  const selectedSubFlowRunSortOption = ref<TaskRunSortValues>('EXPECTED_START_TIME_DESC')

  const subFlowRunTasksFilter = computed<UnionFilters>(() => ({
    sort: selectedSubFlowRunSortOption.value,
    flow_runs: {
      id: {
        any_: [flowRunId.value],
      },
    },
    task_runs: {
      subflow_runs: {
        exists_: true,
      },
    },
  }))

  const subFlowRunTasksSubscription = useUnionFiltersSubscription(taskRunsApi.getTaskRuns, [subFlowRunTasksFilter])
  const subFlowRunTasks = computed(()=> subFlowRunTasksSubscription.response ?? [])
  const subFlowRunTaskIds = computed(() => subFlowRunTasks.value.map(({ id }) => id))

  const subFlowRunsFilter = computed<UnionFilters>(() => ({
    sort: selectedSubFlowRunSortOption.value,
    flow_runs: {
      id: {
        any_: subFlowRunTaskIds.value,
      },
    },
  }))

  const subFlowRunsSubscription = useUnionFiltersSubscription(flowRunsApi.getFlowRuns, [subFlowRunsFilter])
  const subFlowRuns = computed(() => subFlowRunsSubscription.response ?? [])
  const selectedSubFlowRuns = ref([])

  const routeToRadar = (): void => {
    router.push(routes.radar(flowRunId.value))
  }

  function loadMoreSubFlowRuns(): void {
    const unwatch = watch(subFlowRunTaskIds, () => {
      subFlowRunsSubscription.loadMore()
      unwatch()
    })

    subFlowRunTasksSubscription.loadMore()
  }

  function goToFlowRuns(): void {
    router.push(routes.flowRuns())
  }
</script>

<style>
.flow-run__filters { @apply
  flex
  gap-1
  items-center
  justify-end
  mb-2
}

.flow-run__logs {
  min-height: 500px;
}

.flow-run__header-meta { @apply
  flex
  gap-2
  items-center
  xl:hidden
}

.flow-run__meta { @apply
  flex
  flex-col
  gap-3
  items-start
}

.flow-run__small-radar { @apply
  h-[250px]
}

.flow-run__small-radar-link { @apply
  relative
}

/* This is a small hack because the small radar view explicitly overrides cursor for disabled minimaps */
.flow-run__small-radar-link::after {
  content: '';

  @apply
  absolute
  left-0
  top-0
  cursor-pointer
  w-full
  h-full
}
</style>