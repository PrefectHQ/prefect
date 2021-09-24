<template>
  <div>
    <row class="filter-row py-1" hide-scrollbars>
      <button-card
        v-for="filter in premadeFilters"
        :key="filter.label"
        class="filter-card-button"
        shadow="sm"
      >
        <div class="d-flex justify-space-between align-center px-1">
          <div>
            <span class="subheader">{{ filter.count }}</span>
            <span class="ml-1">{{ filter.label }}</span>
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
            :items="run_history_buckets"
            background-color="blue-5"
            show-axis
          />
        </div>
      </Card>

      <Card class="run-duration flex-grow-0" shadow="sm">
        <template v-slot:aside>
          <div class="pl-2 pt-1" style="width: 100px">
            <div class="subheader">10-19m</div>
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
            <div class="subheader">1-59m</div>
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
          {{ flows.length }}
        </span>
      </Tab>
      <Tab href="deployments" class="subheader">
        <i class="pi pi-map-pin-line pi-lg mr-1" />
        Deployments
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'deployments' }"
        >
          {{ datasets['deployments'].length }}
        </span>
      </Tab>
      <Tab href="flow-runs" class="subheader">
        <i class="pi pi-flow-run pi-lg mr-1" />
        Flow Runs
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'flow-runs' }"
        >
          {{ datasets['flow-runs'].length }}
        </span>
      </Tab>
      <Tab href="task-runs" class="subheader">
        <i class="pi pi-task pi-lg mr-1" />
        Task Runs
        <span
          class="result-badge caption ml-1"
          :class="{ active: resultsTab == 'task-runs' }"
        >
          {{ datasets['task-runs'].length }}
        </span>
      </Tab>
    </Tabs>

    <div class="font--secondary caption my-2">
      {{ resultsCount }} Result{{ resultsCount !== 1 ? 's' : '' }}
    </div>

    <transition name="fade" mode="out-in">
      <div v-if="resultsTab == 'flows'">
        <list>
          <flow-list-item v-for="flow in flows" :key="flow.id" :flow="flow" />
        </list>
      </div>

      <div v-else-if="resultsTab == 'deployments'">
        <list>
          <deployment-list-item
            v-for="deployment in datasets['deployments']"
            :key="deployment.id"
            :deployment="deployment"
          />
        </list>
      </div>
      <div v-else-if="resultsTab == 'flow-runs'">
        <list>
          <flow-run-list-item
            v-for="run in datasets['flow-runs']"
            :key="run.id"
            :run="run"
          />
        </list>
      </div>

      <div v-else-if="resultsTab == 'task-runs'">
        <list>
          <task-run-list-item
            v-for="run in datasets['task-runs']"
            :key="run.id"
            :run="run"
          />
        </list>
      </div>
    </transition>
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import { Api, Endpoints, Query, FlowsFilter } from '@/plugins/api'

import {
  default as RunHistoryChart,
  Bucket
} from '@/components/RunHistoryChart/RunHistoryChart.vue'

import BarChart from '@/components/BarChart/BarChart.vue'

import { Flow, FlowRun, Deployment, TaskRun } from '../objects'

import { default as dataset_1 } from '@/util/run_history/24_hours.json'
import { default as dataset_2 } from '@/util/run_history/design.json'
import { default as lateness_dataset_1 } from '@/util/run_lateness/24_hours.json'
import { default as duration_dataset_1 } from '@/util/run_duration/24_hours.json'

// Temporary imports for dummy data
import { default as flowList } from '@/util/objects/flows.json'
import { default as deploymentList } from '@/util/objects/deployments.json'
import { default as flowRunList } from '@/util/objects/flow_runs.json'
import { default as taskRunList } from '@/util/objects/task_runs.json'

@Options({
  components: { BarChart, RunHistoryChart }
})
export default class Dashboard extends Vue {
  flowsFilter: FlowsFilter = {}

  queries: { [key: string]: Query } = {
    flows: Api.query(Endpoints.flows, this.flowsFilter, {
      pollInterval: 2000
    })
  }

  run_history_buckets: Bucket[] = dataset_2

  run_lateness_items: Item[] = lateness_dataset_1.slice(0, 10)
  run_duration_items: Item[] = duration_dataset_1.slice(0, 10)

  datasets: { [key: string]: Flow[] | Deployment[] | FlowRun[] | TaskRun[] } = {
    flows: flowList,
    deployments: deploymentList,
    'flow-runs': flowRunList,
    'task-runs': taskRunList
  }

  premadeFilters: { label: string; count: number }[] = [
    { label: 'Failed Runs', count: 15 },
    { label: 'Late Runs', count: 25 },
    { label: 'Upcoming Runs', count: 75 }
  ]

  resultsTab: string = 'flows'

  get flows() {
    return this.queries.flows.response || []
  }

  get loading() {
    return this.queries.flows.loading
  }

  get resultsCount(): number {
    return this.datasets[this.resultsTab].length
  }

  refetch(): void {
    this.queries.flows.fetch()
  }

  startPolling(): void {
    this.queries.flows.startPolling()
  }

  stopPolling(): void {
    this.queries.flows.stopPolling()
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/views/dashboard.scss';
</style>
