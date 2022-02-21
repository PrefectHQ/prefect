<template>
  <div>
    <row class="filter-row py-1 my-1" hide-scrollbars>
      <ButtonCard
        v-for="filter in premadeFilters"
        :key="filter.label"
        class="filter-card-button"
        shadow="sm"
        @click="applyFilter(filter)"
      >
        <div class="d-flex justify-space-between align-center px-1">
          <div>
            <span class="font--secondary subheader">{{ filter.count }}</span>
            <span class="ml-1 body">{{ filter.label }}</span>
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

    <RouterTabSet :tabs="tabs" class="mt-5">
      <template #after-tab="{ tab }">
        <span class="dashboard__tab-badge caption">{{ getCount(tab.key).toLocaleString() }}</span>
      </template>
      <template #before-tab-content="{ selectedTab }">
        <div class="font--secondary caption my-2" style="min-height: 17px">
          <span
            v-if="getCount(selectedTab.key) > 0"
          >{{ getCount(selectedTab.key).toLocaleString() }} {{ toPluralString('Result', getCount(selectedTab.key)) }}</span>
        </div>
      </template>

      <template #flows="{ tab }">
        <section class="results-section">
          <ResultsList
            v-if="getCount(tab.key) > 0"
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
            v-if="getCount(tab.key) > 0"
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
            v-if="getCount(tab.key) > 0"
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
            v-if="getCount(tab.key) > 0"
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
    </RouterTabSet>

    <hr class="results-hr mt-3">
  </div>
</template>

<script lang="ts" setup>
  import type { UnionFilters, FlowRunsHistoryFilter, DeploymentsFilter } from '@prefecthq/orion-design'
  import { Filter, useFiltersStore, hasFilter, flowsApi } from '@prefecthq/orion-design'
  import { RouterTabSet } from '@prefecthq/orion-design/components'
  import { StateType } from '@prefecthq/orion-design/models'
  import { FiltersQueryService, FilterUrlService, flowRunsApi } from '@prefecthq/orion-design/services'
  import { toPluralString } from '@prefecthq/orion-design/utilities'
  import { subscribe } from '@prefecthq/vue-compositions/src'
  import { computed, ref, ComputedRef } from 'vue'
  import { useRouter } from 'vue-router'
  import LatenessIntervalBarChart from '@/components/LatenessIntervalBarChart.vue'
  import RunHistoryChartCard from '@/components/RunHistoryChart/RunHistoryChart--Card.vue'
  import RunTimeIntervalBarChart from '@/components/RunTimeIntervalBarChart.vue'

  import { Api, Endpoints, Query } from '@/plugins/api'

  const filtersStore = useFiltersStore()
  const router = useRouter()

  const firstFlowRunSubscription = subscribe(flowRunsApi.getFlowRuns.bind(flowRunsApi), [
    {
      limit: 1,
      sort: 'EXPECTED_START_TIME_ASC',
    },
  ])

  const historyStart = computed(() => firstFlowRunSubscription.response.value?.[0]?.expected_start_time)

  const lastFlowRunSubscription = subscribe(flowRunsApi.getFlowRuns.bind(flowRunsApi), [
    {
      limit: 1,
      sort: 'EXPECTED_START_TIME_DESC',
    },
  ])

  const historyEnd = computed(() => lastFlowRunSubscription.response.value?.[0]?.expected_start_time)

  const filter = computed<UnionFilters>(() => {
    return FiltersQueryService.query(filtersStore.all)
  })

  const deploymentFilterOff = ref(false)

  const onFilterOff = () => {
    deploymentFilterOff.value = true
  }

  flowsApi.getFlows(filter.value)

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
      body: countsFilter('Failed', 'FAILED'),
      options: {
        pollInterval: basePollInterval,
      },
    }),
    filter_counts_late: Api.query({
      endpoint: Endpoints.flow_runs_count,
      body: countsFilter('Late', 'FAILED'),
      options: {
        pollInterval: basePollInterval,
      },
    }),
    filter_counts_scheduled: Api.query({
      endpoint: Endpoints.flow_runs_count,
      body: countsFilter('Scheduled', 'SCHEDULED'),
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
        type: 'FAILED',
        name: 'Failed',
      },
      {
        label: 'Late Runs',
        count: typeof late == 'number' ? late.toLocaleString() : '--',
        type: 'SCHEDULED',
        name: 'Late',
      },
      {
        label: 'Upcoming Runs',
        count: typeof scheduled == 'number' ? scheduled.toLocaleString() : '--',
        type: 'SCHEDULED',
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

  const countMap = computed(() => ({
    'flows': flowsCount.value,
    'deployments': deploymentsCount.value,
    'flow_runs': flowRunsCount.value,
    'task_runs': taskRunsCount.value,
  }))

  const getCount = (key: 'flows'|'deployments'|'flow_runs'|'task_runs'): number => {
    return countMap.value[key]
  }

  const tabs = [
    {
      title: 'Flows',
      key: 'flows',
      route: {
        name: 'Dashboard',
        hash: 'flows',
      },
      icon: 'pi-flow',
    },
    {
      title: 'Deployments',
      key: 'deployments',
      route: {
        name: 'Dashboard',
        hash: 'deployments',
      },
      icon: 'pi-map-pin-line',
    },
    {
      title: 'Flow Runs',
      key: 'flow_runs',
      route: {
        name: 'Dashboard',
        hash: 'flow_runs',
      },
      icon: 'pi-flow-run',
    },
    {
      title: 'Task Runs',
      key: 'task_runs',
      route: {
        name: 'Dashboard',
        hash: 'task_runs',
      },
      icon: 'pi-task',
    },
  ]

  const applyFilter = (filter: PremadeFilter) => {
    const filterToAdd: Required<Filter> = {
      object: 'flow_run',
      property: 'state',
      type: 'state',
      operation: 'or',
      value: [filter.type],
    }

    if (hasFilter(filtersStore.all, filterToAdd)) {
      return
    }

    const service = new FilterUrlService(router)

    service.add(filterToAdd)
  }
</script>

<style lang="scss">
@use '@/styles/views/dashboard.scss';

.dashboard__tab-badge {
    background-color: $white;
    border-radius: 16px;
    font-weight: 400;
    padding: 0 8px;
    min-width: 24px;
    transition: 150ms all;
}
.tab-set__tab--active {
    background-color: $primary;
    color: $white;
    .dashboard__tab-badge {
        background-color: $primary;
        color: $white;
    }
}
.results-section {
  display: flex;
  align-items: stretch;
  justify-content: stretch;
  flex-direction: column;
}
</style>
