<template>
  <list-item class="list-item--flow d-flex align-start justify-start">
    <i class="item--icon pi pi-flow text--grey-40 align-self-start" />
    <div
      class="
        item--title
        ml-2
        d-flex
        flex-column
        justify-center
        align-self-start
      "
    >
      <h2>
        {{ item.name }}
      </h2>

      <div class="nowrap tag-container d-flex align-bottom">
        <Tag
          v-for="tag in item.tags"
          :key="tag"
          color="secondary-pressed"
          class="caption font-weight-semibold mr-1"
          icon="pi-label"
          flat
        >
          {{ tag }}
        </Tag>
      </div>
    </div>

    <div v-breakpoints="'sm'" class="ml-auto nowrap">
      <rounded-button class="mr-1">
        {{ flowRunCount }} flow run{{ flowRunCount === 1 ? '' : 's' }}
      </rounded-button>

      <rounded-button class="mr-1">
        {{ taskRunCount }} task run{{ taskRunCount === 1 ? '' : 's' }}
      </rounded-button>
    </div>

    <div v-breakpoints="'md'" class="chart-container">
      <RunHistoryChart
        :items="flowRunBuckets"
        :interval-start="start"
        :interval-end="end"
        :interval-seconds="intervalSeconds"
        :padding="{ top: 3, bottom: 3, left: 3, right: 3, middle: 2 }"
      />
    </div>
  </list-item>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { Flow } from '@/typings/objects'
import RunHistoryChart from '@/components/RunHistoryChart/RunHistoryChart--Chart.vue'

import { Api, Query, Endpoints, FlowRunsHistoryFilter } from '@/plugins/api'
import { Buckets } from '@/typings/run_history'

class Props {
  item = prop<Flow>({ required: true })
}

@Options({ components: { RunHistoryChart } })
export default class ListItemFlow extends Vue.with(Props) {
  start = new Date()
  end = new Date()
  intervalSeconds = 330

  queries: { [key: string]: Query } = {
    flow_run_history: Api.query({
      endpoint: Endpoints.flow_runs_history,
      body: this.flowRunHistoryFilter
    }),
    flow_run_count: Api.query({
      endpoint: Endpoints.flow_runs_count,
      body: {
        flows: this.flowFilter
      }
    }),
    task_run_count: Api.query({
      endpoint: Endpoints.task_runs_count,
      body: {
        flows: this.flowFilter
      }
    })
  }

  get flowFilter(): any {
    return {
      id: {
        any_: [this.item.id]
      }
    }
  }

  get flowRunBuckets(): Buckets {
    return this.queries.flow_run_history?.response || []
  }

  get flowRunHistoryFilter(): FlowRunsHistoryFilter {
    return {
      history_start: this.start.toISOString(),
      history_end: this.end.toISOString(),
      history_interval_seconds: this.intervalSeconds,
      flows: this.flowFilter
    }
  }

  beforeCreate(): void {
    this.start.setHours(this.start.getHours() - 1)
    this.start.setMinutes(0)
    this.start.setSeconds(0)
    this.start.setMilliseconds(0)
    this.end.setHours(this.end.getHours() + 1)
    this.end.setMinutes(0)
    this.end.setSeconds(0)
    this.end.setMilliseconds(0)
  }

  mounted(): void {
    this.queries.flow_run_history.body = this.flowRunHistoryFilter
    this.queries.flow_run_history.startPolling()
  }

  get flowRunCount(): number {
    return this.queries.flow_run_count.response || 0
  }

  get taskRunCount(): number {
    return this.queries.task_run_count.response || 0
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/list-item--flow.scss';
</style>
