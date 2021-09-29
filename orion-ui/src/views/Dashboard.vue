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

    <div class="chart-section">
      <Card class="run-history" shadow="sm">
        <template v-slot:header>
          <div class="subheader py-1 px-2">Run History</div>
        </template>

        <div class="px-2 pb-1 flex-grow-1">
          <RunHistoryChart
            v-if="run_history_buckets && run_history_buckets.length"
            :items="run_history_buckets"
            background-color="blue-5"
            show-axis
          />
          <div v-else class="font--secondary subheader no-data"> -- </div>
        </div>
      </Card>

      <Card class="run-duration flex-grow-0" shadow="sm">
        <template v-slot:aside>
          <div class="pl-2 pt-1" style="width: 100px">
            <div class="font--secondary subheader">--</div>
            <div class="body">Duration</div>
          </div>
        </template>
        <div class="chart px-1">
          <BarChart :items="run_duration_items" height="117px" />
        </div>
      </Card>

      <Card class="run-lateness flex-grow-0" shadow="sm">
        <template v-slot:aside>
          <div class="pl-2 pt-1" style="width: 100px">
            <div class="font--secondary subheader">--</div>
            <div class="body">Lateness</div>
          </div>
        </template>
        <div class="chart px-1">
          <BarChart :items="run_lateness_items" height="117px" />
        </div>
      </Card>
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

    <div v-if="resultsCount > 0" class="font--secondary caption my-2">
      {{ resultsCount }} Result{{ resultsCount !== 1 ? 's' : '' }}
    </div>

    <section
      class="results-section d-flex flex-column align-stretch justify-stretch"
    >
      <transition name="tab-fade" css>
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
  DeploymentsFilter,
  FlowRunsFilter,
  TaskRunsFilter
} from '@/plugins/api'

import {
  default as RunHistoryChart,
  Bucket
} from '@/components/RunHistoryChart/RunHistoryChart.vue'

import BarChart from '@/components/BarChart/BarChart.vue'

import { Flow, FlowRun, Deployment, TaskRun } from '@/types/objects'

@Options({
  components: { BarChart, RunHistoryChart },
  watch: {
    resultsTab(val) {
      this.$router.push({ hash: `#${val}` })
    }
  }
})
export default class Dashboard extends Vue {
  flowsFilter: FlowsFilter = {}

  queries: { [key: string]: Query } = {
    deployments: Api.query(Endpoints.deployments_count, this.flowsFilter, {}),
    flows: Api.query(Endpoints.flows_count, this.flowsFilter, {}),
    flow_runs: Api.query(Endpoints.flow_runs_count, this.flowsFilter, {}),
    task_runs: Api.query(Endpoints.task_runs_count, this.flowsFilter, {})
  }

  run_history_buckets: Bucket[] = []

  run_lateness_items: Item[] = []
  run_duration_items: Item[] = []

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

  get loading() {
    return (
      this.queries.flows.loading ||
      this.queries.deployments.loading ||
      this.queries.flow_runs.loading ||
      this.queries.task_runs.loading
    )
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

  created() {
    this.resultsTab = this.$route.hash?.substr(1) || 'flows'
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/views/dashboard.scss';

.tab-fade-enter-active,
.tab-fade-leave-active {
  opacity: 0;
  position: absolute;
  transition: opacity 150ms ease;
}
</style>
