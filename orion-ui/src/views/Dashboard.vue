<template>
  <div>
    <row class="filter-row py-1 my-1" hide-scrollbars>
      <button-card
        v-for="filter in premadeFilters"
        :key="filter.label"
        class="filter-card-button"
        shadow="sm"
      >
        <div class="d-flex justify-space-between align-center px-1">
          <div>
            <span class="font--secondary subheader">
              {{ filter.count || '--' }}
            </span>
            <span class="ml-1 body">{{ filter.label }}</span>
          </div>
          <i class="pi pi-filter-3-line pi-lg" />
        </div>
      </button-card>
    </row>

    <!-- These can be used to paginate the chart -->
    <!-- v-if="false" -->
    <IconButton icon="pi-arrow-left-line" @click="previous30Minutes" />
    <!-- v-if="false" -->
    <IconButton icon="pi-arrow-right-line" @click="next30Minutes" />

    <div class="chart-section">
      <RunHistoryChartCard class="run-history" :filter="flowRunHistoryFilter" />

      <IntervalBarChartCard
        title="Duration"
        endpoint="flow_runs_history"
        state-bucket-key="sum_estimated_run_time"
        height="77px"
        :filter="flowRunStatsFilter"
        class="run-duration flex-grow-0"
      />

      <IntervalBarChartCard
        title="Lateness"
        endpoint="flow_runs_history"
        state-bucket-key="sum_estimated_lateness"
        height="77px"
        :filter="flowRunStatsFilter"
        class="run-lateness flex-grow-0"
      />
    </div>

    <Tabs v-model="resultsTab" class="mt-5">
      <Tab href="flows" class="subheader">
        <i class="pi pi-flow pi-lg mr-1" />
        Flows
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'flows' }"
        >
          {{ flowsCount }}
        </span>
      </Tab>
      <Tab href="deployments" class="subheader">
        <i class="pi pi-map-pin-line pi-lg mr-1" />
        Deployments
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'deployments' }"
        >
          {{ deploymentsCount }}
        </span>
      </Tab>
      <Tab href="flow_runs" class="subheader">
        <i class="pi pi-flow-run pi-lg mr-1" />
        Flow Runs
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'flow_runs' }"
        >
          {{ flowRunsCount }}
        </span>
      </Tab>
      <Tab href="task_runs" class="subheader">
        <i class="pi pi-task pi-lg mr-1" />
        Task Runs
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'task_runs' }"
        >
          {{ taskRunsCount }}
        </span>
      </Tab>
    </Tabs>

    <div class="font--secondary caption my-2" style="min-height: 17px">
      <span v-show="resultsCount > 0">
        {{ resultsCount }} Result{{ resultsCount !== 1 ? 's' : '' }}
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
          <h2> No Results Found </h2>
          <div v-show="resultsTab == 'deployments'" class="mt-2">
            Deployments can only be created using the Prefect CLI
          </div>
        </div>

        <results-list
          v-else-if="resultsTab == 'flows'"
          key="flows"
          :filter="flowFilter"
          component="flow-list-item"
          endpoint="flows"
        />

        <results-list
          v-else-if="resultsTab == 'deployments'"
          key="deployments"
          :filter="deploymentFilter"
          component="deployment-list-item"
          endpoint="deployments"
        />

        <results-list
          v-else-if="resultsTab == 'flow_runs'"
          key="flow_runs"
          :filter="flowRunFilter"
          component="flow-run-list-item"
          endpoint="flow_runs"
        />

        <results-list
          v-else-if="resultsTab == 'task_runs'"
          key="task_runs"
          :filter="taskRunFilter"
          component="task-run-list-item"
          endpoint="task_runs"
        />
      </transition>
    </section>
    <hr class="results-hr mt-3" />
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import {
  Api,
  Endpoints,
  Query,
  FlowsFilter,
  FlowRunsHistoryFilter,
  DeploymentsFilter,
  FlowRunsFilter,
  TaskRunsFilter
} from '@/plugins/api'

import RunHistoryChartCard from '@/components/RunHistoryChart/RunHistoryChart--Card.vue'

import IntervalBarChartCard from '@/components/IntervalBarChart/IntervalBarChart--Card.vue'

@Options({
  components: { IntervalBarChartCard, RunHistoryChartCard },
  watch: {
    resultsTab(val) {
      this.$router.push({ hash: `#${val}` })
    }
  }
})
export default class Dashboard extends Vue {
  queries: { [key: string]: Query } = {
    deployments: Api.query({
      endpoint: Endpoints.deployments_count,
      body: this.deploymentFilter,
      options: {
        pollInterval: 10000
      }
    }),
    flows: Api.query({
      endpoint: Endpoints.flows_count,
      body: this.flowFilter,
      options: {
        pollInterval: 10000
      }
    }),
    flow_runs: Api.query({
      endpoint: Endpoints.flow_runs_count,
      body: this.flowRunFilter,
      options: {
        pollInterval: 10000
      }
    }),
    task_runs: Api.query({
      endpoint: Endpoints.task_runs_count,
      body: this.taskRunFilter,
      options: {
        pollInterval: 10000
      }
    })
  }

  premadeFilters: { label: string; count: number | null }[] = [
    { label: 'Failed Runs', count: null },
    { label: 'Late Runs', count: null },
    { label: 'Upcoming Runs', count: null }
  ]

  resultsTab: string | null = null

  get flowsCount(): number {
    return this.queries.flows?.response || 0
  }

  get deploymentsCount(): number {
    return this.queries.deployments?.response || 0
  }

  get flowRunsCount(): number {
    return this.queries.flow_runs?.response || 0
  }

  get taskRunsCount(): number {
    return this.queries.task_runs?.response || 0
  }

  get loading(): boolean {
    return (
      this.queries.flows.loading.value ||
      this.queries.deployments.loading.value ||
      this.queries.flow_runs.loading.value ||
      this.queries.task_runs.loading.value
    )
  }

  start = new Date()
  end = new Date()

  get flowRunHistoryFilter(): FlowRunsHistoryFilter {
    return {
      history_start: this.start.toISOString(),
      history_end: this.end.toISOString(),
      history_interval_seconds: 60
    }
  }

  get flowRunStatsFilter(): FlowRunsHistoryFilter {
    return {
      ...this.flowRunHistoryFilter,
      history_interval_seconds:
        this.flowRunHistoryFilter.history_interval_seconds * 2
    }
  }

  get flowFilter(): FlowsFilter {
    return {}
  }

  get flowRunFilter(): FlowRunsFilter {
    return {}
  }

  get taskRunFilter(): TaskRunsFilter {
    return {}
  }

  get deploymentFilter(): DeploymentsFilter {
    return {}
  }

  get resultsCount(): number {
    if (!this.resultsTab) return 0
    return this.queries[this.resultsTab].response || 0
  }

  previous30Minutes(): void {
    const start = this.start
    const end = this.end

    start.setMinutes(start.getMinutes() - 10)
    end.setMinutes(end.getMinutes() - 10)

    this.start = new Date(start)
    this.end = new Date(end)
  }
  next30Minutes(): void {
    const start = this.start
    const end = this.end

    start.setMinutes(start.getMinutes() + 10)
    end.setMinutes(end.getMinutes() + 10)

    this.start = new Date(start)
    this.end = new Date(end)
  }

  beforeCreate(): void {
    this.resultsTab = this.$route.hash?.substr(1) || 'flows'

    this.start.setMinutes(this.start.getMinutes() - 10)
    this.start.setSeconds(0)
    this.start.setMilliseconds(0)
    this.end.setHours(this.end.getHours() + 1)
    this.end.setMinutes(0)
    this.end.setSeconds(0)
    this.end.setMilliseconds(0)
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/views/dashboard.scss';

.tab-fade-enter-active,
.tab-fade-leave-active {
  opacity: 0;
  transition: opacity 150ms ease;
}
</style>
