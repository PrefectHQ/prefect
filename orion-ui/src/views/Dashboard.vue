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
            <span class="font--secondary subheader">
              {{ filter.count }}
            </span>
            <span class="ml-1 body">{{ filter.label }}</span>
          </div>
          <i class="pi pi-filter-3-line pi-lg text--grey-80" />
        </div>
      </ButtonCard>
    </row>

    <div class="chart-section">
      <RunHistoryChartCard class="run-history" :filter="flowRunHistoryFilter" />

      <RunTimeIntervalBarChart
        :filter="flowRunStatsFilter"
        class="run-duration flex-grow-0"
      />

      <LatenessIntervalBarChart
        :filter="flowRunStatsFilter"
        class="run-lateness flex-grow-0"
      />
    </div>

    <Tabs v-model="resultsTab" class="mt-5">
      <Tab href="flows" class="subheader">
        <i
          class="pi pi-flow mr-1"
          :class="resultsTab == 'flows' ? 'text--primary' : 'text--grey-40'"
        />
        Flows
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'flows' }"
        >
          {{ flowsCount.toLocaleString() }}
        </span>
      </Tab>
      <Tab href="deployments" class="subheader">
        <i
          class="pi pi-map-pin-line mr-1"
          :class="
            resultsTab == 'deployments' ? 'text--primary' : 'text--grey-40'
          "
        />
        Deployments
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'deployments' }"
        >
          {{ deploymentsCount.toLocaleString() }}
        </span>
      </Tab>
      <Tab href="flow_runs" class="subheader">
        <i
          class="pi pi-flow-run mr-1"
          :class="resultsTab == 'flow_runs' ? 'text--primary' : 'text--grey-40'"
        />
        Flow Runs
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'flow_runs' }"
        >
          {{ flowRunsCount.toLocaleString() }}
        </span>
      </Tab>
      <Tab href="task_runs" class="subheader">
        <i
          class="pi pi-task mr-1"
          :class="resultsTab == 'task_runs' ? 'text--primary' : 'text--grey-40'"
        />
        Task Runs
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'task_runs' }"
        >
          {{ taskRunsCount.toLocaleString() }}
        </span>
      </Tab>
    </Tabs>

    <div class="font--secondary caption my-2" style="min-height: 17px">
      <span v-show="resultsCount > 0">
        {{ resultsCount.toLocaleString() }} Result{{
          resultsCount !== 1 ? 's' : ''
        }}
      </span>
    </div>

    <section
      class="results-section d-flex flex-column align-stretch justify-stretch"
    >
      <transition name="tab-fade" mode="out-in" css>
        <div
          v-if="resultsCount === 0"
          class="text-center my-8"
          key="no-results"
        >
          <template v-if="resultsTab == 'deployments'">
            <h2> No scheduled deployments found </h2>
            <div class="my-2">
              Deployments can only be created using the Prefect CLI
            </div>
            <Button color="alternate" @click="onFilterOff">
              Show all deployments
            </Button>
          </template>
          <h2 v-else> No results found </h2>
        </div>

        <ResultsList
          v-else-if="resultsTab == 'flows'"
          key="flows"
          :filter="filter"
          component="ListItemFlow"
          endpoint="flows"
          :poll-interval="15000"
        />

        <ResultsList
          v-else-if="resultsTab == 'deployments'"
          key="deployments"
          :filter="deploymentsFilter"
          component="ListItemDeployment"
          endpoint="deployments"
          :poll-interval="15000"
        />

        <ResultsList
          v-else-if="resultsTab == 'flow_runs'"
          key="flow_runs"
          :filter="filter"
          component="ListItemFlowRun"
          endpoint="flow_runs"
          :poll-interval="7500"
        />

        <ResultsList
          v-else-if="resultsTab == 'task_runs'"
          key="task_runs"
          :filter="filter"
          component="ListItemTaskRun"
          endpoint="task_runs"
          :poll-interval="10000"
        />
      </transition>
    </section>
    <hr class="results-hr mt-3" />
  </div>
</template>

<script lang="ts" setup>
import { computed, ref, Ref, onBeforeMount, ComputedRef, watch } from 'vue'
import RunHistoryChartCard from '@/components/RunHistoryChart/RunHistoryChart--Card.vue'
import RunTimeIntervalBarChart from '@/components/RunTimeIntervalBarChart.vue'
import LatenessIntervalBarChart from '@/components/LatenessIntervalBarChart.vue'

import {
  Api,
  Endpoints,
  Query,
  FlowsFilter,
  FlowRunsHistoryFilter,
  DeploymentsFilter,
  FlowRunsFilter,
  TaskRunsFilter,
  BaseFilter
} from '@/plugins/api'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import router from '@/router'

const store = useStore()
const route = useRoute()

const resultsTab: Ref<string | null> = ref(null)

const filter = computed<
  FlowsFilter | FlowRunsFilter | TaskRunsFilter | DeploymentsFilter
>(() => {
  return { ...store.getters.composedFilter }
})

const deploymentFilterOff = ref(false)

const onFilterOff = () => {
  deploymentFilterOff.value = true
}
const deploymentsFilter = computed<object | DeploymentsFilter>(() => {
  if (deploymentFilterOff.value) {
    return {}
  }
  return filter.value
})

const start = computed<Date>(() => {
  return store.getters.start
})

const end = computed<Date>(() => {
  return store.getters.end
})

const countsFilter = (
  state_name: string,
  state_type: string
): ComputedRef<BaseFilter> => {
  return computed<BaseFilter>((): BaseFilter => {
    let start_time: { after_?: string; before_?: string } | undefined =
      undefined

    if (start.value || end.value) {
      start_time = {}
      if (start.value) start_time.after_ = start.value?.toISOString()
      if (end.value) start_time.before_ = end.value?.toISOString()
    }

    const composedFilter = store.getters.composedFilter

    const stateType = state_name == 'Failed'
    composedFilter.flow_runs.state = {
      [stateType ? 'type' : 'name']: {
        any_: [stateType ? state_type : state_name]
      }
    }

    return {
      ...composedFilter
    }
  })
}

const basePollInterval = 30000

const queries: { [key: string]: Query } = {
  deployments: Api.query({
    endpoint: Endpoints.deployments_count,
    body: deploymentsFilter,
    options: {
      pollInterval: basePollInterval
    }
  }),
  flows: Api.query({
    endpoint: Endpoints.flows_count,
    body: filter,
    options: {
      pollInterval: basePollInterval
    }
  }),
  task_runs: Api.query({
    endpoint: Endpoints.task_runs_count,
    body: filter,
    options: {
      pollInterval: basePollInterval
    }
  }),
  flow_runs: Api.query({
    endpoint: Endpoints.flow_runs_count,
    body: filter,
    options: {
      pollInterval: basePollInterval
    }
  }),
  filter_counts_failed: Api.query({
    endpoint: Endpoints.flow_runs_count,
    body: countsFilter('Failed', 'FAILED'),
    options: {
      pollInterval: basePollInterval
    }
  }),
  filter_counts_late: Api.query({
    endpoint: Endpoints.flow_runs_count,
    body: countsFilter('Late', 'FAILED'),
    options: {
      pollInterval: basePollInterval
    }
  }),
  filter_counts_scheduled: Api.query({
    endpoint: Endpoints.flow_runs_count,
    body: countsFilter('Scheduled', 'SCHEDULED'),
    options: {
      pollInterval: basePollInterval
    }
  })
}

const premadeFilters = computed<
  { [key: string]: string | undefined | number }[]
>(() => {
  const failed = queries.filter_counts_failed.response.value
  const late = queries.filter_counts_late.response.value
  const scheduled = queries.filter_counts_scheduled.response.value
  return [
    {
      label: 'Failed Runs',
      count: typeof failed == 'number' ? failed.toLocaleString() : '--',
      type: 'FAILED',
      name: 'Failed'
    },
    {
      label: 'Late Runs',
      count: typeof late == 'number' ? late.toLocaleString() : '--',
      type: 'SCHEDULED',
      name: 'Late'
    },
    {
      label: 'Upcoming Runs',
      count: typeof scheduled == 'number' ? scheduled.toLocaleString() : '--',
      type: 'SCHEDULED',
      name: 'Scheduled'
    }
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

const interval = computed<number>(() => {
  return store.getters.baseInterval
})

const flowRunHistoryFilter = computed<FlowRunsHistoryFilter>(() => {
  return {
    history_start: start.value.toISOString(),
    history_end: end.value.toISOString(),
    history_interval_seconds: interval.value,
    ...store.getters.composedFilter
  }
})

const flowRunStatsFilter = computed<FlowRunsHistoryFilter>(() => {
  return {
    ...flowRunHistoryFilter.value,
    history_interval_seconds: interval.value * 2,
    ...store.getters.composedFilter
  }
})

const resultsCount = computed<number>(() => {
  if (!resultsTab.value) return 0
  return queries[resultsTab.value].response.value || 0
})

const applyFilter = (filter: {
  [key: string]: string | undefined | number
}) => {
  const globalFilter = { ...store.getters.globalFilter }
  globalFilter.flow_runs.states = [{ name: filter.name, type: filter.type }]
  store.commit('globalFilter', globalFilter)
}

watch([resultsTab], () => {
  router.push({ hash: `#${resultsTab.value}` })
})

onBeforeMount(() => {
  resultsTab.value = route.hash?.substr(1) || 'flows'
})
</script>

<style lang="scss" scoped>
@use '@/styles/views/dashboard.scss';

.tab-fade-enter-active,
.tab-fade-leave-active {
  opacity: 0;
  transition: opacity 150ms ease;
}
</style>
