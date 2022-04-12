<template>
  <div>
    <row class="filter-row py-1 my-1" hide-scrollbars>
      <ButtonCard
        v-for="premadeFilter in premadeFilters"
        :key="premadeFilter.label"
        class="filter-card-button"
        shadow="sm"
        @click="applyFilter(premadeFilter)"
      >
        <div class="d-flex justify-space-between align-center px-1">
          <div>
            <span class="font--secondary subheader">{{ premadeFilter.count }}</span>
            <span class="ml-1 body">{{ premadeFilter.label }}</span>
          </div>
          <i class="pi pi-filter-3-line pi-lg text--grey-80" />
        </div>
      </ButtonCard>
    </row>

    <div class="chart-section">
      <RunHistoryChartCard class="run-history" :filter="flowRunHistoryFilter" />

      <RunTimeIntervalBarChart :filter="flowRunStatsFilter" class="run-duration flex-grow-0" />

      <LatenessIntervalBarChart :filter="flowRunStatsFilter" class="run-lateness flex-grow-0" />
    </div>

    <ListTabSet :tabs="tabs" class="mt-5">
      <template #flows="{ tab }">
        <section class="results-section">
          <ResultsList
            v-if="tab.count > 0"
            key="flows"
            :filter="filter"
            component="ListItemFlow"
            endpoint="flows"
            :poll-interval="15000"
          />
          <div v-else class="text-center my-8">
            <h2>No results found</h2>
          </div>
        </section>
      </template>

      <template #deployments="{ tab }">
        <section class="results-section">
          <ResultsList
            v-if="tab.count > 0"
            key="deployments"
            :filter="deploymentsFilter"
            component="ListItemDeployment"
            endpoint="deployments"
            :poll-interval="15000"
          />
          <div v-else class="text-center my-8">
            <h2>No scheduled deployments found</h2>
            <div class="my-2">
              Deployments can only be created using the Prefect CLI
            </div>
            <Button color="alternate" @click="onFilterOff">
              Show all deployments
            </Button>
          </div>
        </section>
      </template>

      <template #flow_runs="{ tab }">
        <section class="results-section">
          <ResultsList
            v-if="tab.count > 0"
            key="flow_runs"
            :filter="filter"
            component="ListItemFlowRun"
            endpoint="flow_runs"
            :poll-interval="7500"
          />
          <div v-else class="text-center my-8">
            <h2>No results found</h2>
          </div>
        </section>
      </template>

      <template #task_runs="{ tab }">
        <section class="results-section d-flex flex-column align-stretch justify-stretch">
          <ResultsList
            v-if="tab.count > 0"
            key="task_runs"
            :filter="filter"
            component="ListItemTaskRun"
            endpoint="task_runs"
            :poll-interval="10000"
          />
          <div v-else class="text-center my-8">
            <h2>No results found</h2>
          </div>
        </section>
      </template>
    </ListTabSet>

    <hr class="results-hr mt-3">
  </div>
</template>

<script lang="ts" setup>
  import {
    UnionFilters,
    FlowRunsHistoryFilter,
    DeploymentsFilter,
    useFiltersStore,
    ListTabSet,
    ListRouterTab,
    StateType,
    FiltersQueryService,
    FilterUrlService,
    States,
    ButtonCard
  } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref, ComputedRef } from 'vue'
  import { useRouter } from 'vue-router'
  import LatenessIntervalBarChart from '@/components/LatenessIntervalBarChart.vue'
  import RunHistoryChartCard from '@/components/RunHistoryChart/RunHistoryChart--Card.vue'
  import RunTimeIntervalBarChart from '@/components/RunTimeIntervalBarChart.vue'
  import { Api, Endpoints, Query } from '@/plugins/api'
  import { flowRunsApi } from '@/services/flowRunsApi'

  const filtersStore = useFiltersStore()
  const router = useRouter()

  const firstFlowRunSubscription = useSubscription(flowRunsApi.getFlowRuns, [
    {
      limit: 1,
      sort: 'EXPECTED_START_TIME_ASC',
    },
  ])

  const historyStart = computed(() => firstFlowRunSubscription.response?.[0]?.expectedStartTime)

  const lastFlowRunSubscription = useSubscription(flowRunsApi.getFlowRuns, [
    {
      limit: 1,
      sort: 'EXPECTED_START_TIME_DESC',
    },
  ])

  const historyEnd = computed(() => lastFlowRunSubscription.response?.[0]?.expectedStartTime)

  const filter = computed<UnionFilters>(() => {
    return FiltersQueryService.query(filtersStore.all)
  })

  const deploymentFilterOff = ref(false)

  const onFilterOff = (): void => {
    deploymentFilterOff.value = true
  }

  const deploymentsFilter = computed<object | DeploymentsFilter>(() => {
    if (deploymentFilterOff.value) {
      return {}
    }
    return filter.value
  })

  const countsFilter = (
    state_name: string,
    state_type: string,
  ): ComputedRef<UnionFilters> => {
    return computed<UnionFilters>((): UnionFilters => {
      const countsFilter = FiltersQueryService.query(filtersStore.all)
      const stateType = state_name == 'Failed'

      countsFilter.flow_runs = {
        ...countsFilter.flow_runs,
        state: {
          [stateType ? 'type' : 'name']: {
            any_: [stateType ? state_type : state_name],
          },
        },
      }

      return countsFilter
    })
  }

  const basePollInterval = 30000

  const queries: Record<string, Query> = {
    deployments: Api.query({
      endpoint: Endpoints.deployments_count,
      body: deploymentsFilter,
      options: {
        pollInterval: basePollInterval,
      },
    }),
    flows: Api.query({
      endpoint: Endpoints.flows_count,
      body: filter,
      options: {
        pollInterval: basePollInterval,
      },
    }),
    task_runs: Api.query({
      endpoint: Endpoints.task_runs_count,
      body: filter,
      options: {
        pollInterval: basePollInterval,
      },
    }),
    flow_runs: Api.query({
      endpoint: Endpoints.flow_runs_count,
      body: filter,
      options: {
        pollInterval: basePollInterval,
      },
    }),
    filter_counts_failed: Api.query({
      endpoint: Endpoints.flow_runs_count,
      body: countsFilter('Failed', States.FAILED),
      options: {
        pollInterval: basePollInterval,
      },
    }),
    filter_counts_late: Api.query({
      endpoint: Endpoints.flow_runs_count,
      body: countsFilter('Late', States.FAILED),
      options: {
        pollInterval: basePollInterval,
      },
    }),
    filter_counts_scheduled: Api.query({
      endpoint: Endpoints.flow_runs_count,
      body: countsFilter('Scheduled', States.SCHEDULED),
      options: {
        pollInterval: basePollInterval,
      },
    }),
  }

  type PremadeFilter = {
    label: string,
    count: string,
    type: StateType,
    name: string,
  }
  const premadeFilters = computed<PremadeFilter[]>(() => {
    const failed = queries.filter_counts_failed.response.value
    const late = queries.filter_counts_late.response.value
    const scheduled = queries.filter_counts_scheduled.response.value
    return [
      {
        label: 'Failed Runs',
        count: typeof failed == 'number' ? failed.toLocaleString() : '--',
        type: States.FAILED,
        name: 'Failed',
      },
      {
        label: 'Late Runs',
        count: typeof late == 'number' ? late.toLocaleString() : '--',
        type: States.SCHEDULED,
        name: 'Late',
      },
      {
        label: 'Upcoming Runs',
        count: typeof scheduled == 'number' ? scheduled.toLocaleString() : '--',
        type: States.SCHEDULED,
        name: 'Scheduled',
      },
    ]
  })

  const flowsCount = computed<number>(() => {
    return queries.flows?.response.value || 0
  })

  const deploymentsCount = computed<number>(() => {
    return queries.deployments?.response.value || 0
  })

  const flowRunsCount = computed<number>(() => {
    return queries.flow_runs?.response.value || 0
  })

  const taskRunsCount = computed<number>(() => {
    return queries.task_runs?.response.value || 0
  })

  const flowRunHistoryFilter = computed<FlowRunsHistoryFilter>(() => {
    if (historyStart.value && historyEnd.value) {
      return FiltersQueryService.flowHistoryQuery(filtersStore.all, new Date(historyStart.value), new Date(historyEnd.value))
    }

    return FiltersQueryService.flowHistoryQuery(filtersStore.all)
  })

  const flowRunStatsFilter = computed<FlowRunsHistoryFilter>(() => {
    const interval = flowRunHistoryFilter.value.history_interval_seconds

    return {
      ...flowRunHistoryFilter.value,
      history_interval_seconds: interval * 2,
    }
  })

  const tabs = computed<ListRouterTab[]>(() => [
    {
      title: 'Flows',
      key: 'flows',
      route: {
        name: 'Dashboard',
        hash: 'flows',
      },
      icon: 'pi-flow',
      count: flowsCount.value,
    },
    {
      title: 'Deployments',
      key: 'deployments',
      route: {
        name: 'Dashboard',
        hash: 'deployments',
      },
      icon: 'pi-map-pin-line',
      count: deploymentsCount.value,
    },
    {
      title: 'Flow Runs',
      key: 'flow_runs',
      route: {
        name: 'Dashboard',
        hash: 'flow_runs',
      },
      icon: 'pi-flow-run',
      count: flowRunsCount.value,
    },
    {
      title: 'Task Runs',
      key: 'task_runs',
      route: {
        name: 'Dashboard',
        hash: 'task_runs',
      },
      icon: 'pi-task',
      count: taskRunsCount.value,
    },
  ])

  const applyFilter = (filter: PremadeFilter): void => {
    const service = new FilterUrlService(router)

    service.add({
      object: 'flow_run',
      property: 'state',
      type: 'state',
      operation: 'or',
      value: [filter.type],
    })
  }
</script>

<style lang="scss">
@use '@/styles/views/dashboard.scss';

.results-section {
  display: flex;
  align-items: stretch;
  justify-content: stretch;
  flex-direction: column;
}
</style>