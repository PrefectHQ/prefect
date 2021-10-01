<template>
  <list-item class="list-item--flow-run d-flex align-start justify-start">
    <!-- For a later date... maybe -->
    <!-- :class="state + '-border'" -->

    <i
      class="item--icon pi text--grey-40 align-self-start"
      :class="`pi-${state}`"
    />
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
        <span
          v-skeleton="!flow.name"
          class="text--grey-40"
          style="min-width: 40px"
        >
          {{ flow.name }} /
        </span>
        {{ item.name }}
      </h2>

      <div class="tag-container nowrap d-flex align-bottom">
        <span
          class="run-state correct-text caption mr-1"
          :class="state + '-bg'"
        >
          {{ state }}
        </span>

        <Tag
          v-for="tag in tags"
          :key="tag"
          color="secondary-pressed"
          class="font--primary caption font-weight-semibold mr-1"
          icon="pi-label"
          flat
        >
          {{ tag }}
        </Tag>
      </div>
    </div>

    <div v-breakpoints="'sm'" class="ml-auto mr-1 nowrap">
      <rounded-button class="mr-1">
        {{ taskRunCount }} task run{{ taskRunCount == 1 ? '' : 's' }}
      </rounded-button>
    </div>

    <div v-breakpoints="'md'" class="chart-container mr-2">
      <RunHistoryChart
        :items="taskRunHistory"
        :interval-start="start"
        :interval-end="end"
        :interval-seconds="store.getters.globalFilter.intervalSeconds"
        static-median
        :padding="{ top: 3, bottom: 3, left: 6, right: 6, middle: 2 }"
      />
    </div>

    <div class="font--secondary item--duration mr-2">
      {{ duration }}
    </div>

    <i class="pi pi-arrow-right-s-line text--grey-80" />
  </list-item>
</template>

<script lang="ts" setup>
import { defineProps, computed } from 'vue'
import RunHistoryChart from '@/components/RunHistoryChart/RunHistoryChart--Chart.vue'
import {
  Api,
  Query,
  Endpoints,
  TaskRunsFilter,
  FlowsFilter
} from '@/plugins/api'
import { FlowRun } from '@/typings/objects'
import { Buckets } from '@/typings/run_history'
import { useStore } from 'vuex'
import { secondsToApproximateString } from '@/util/util'

const store = useStore()
const props = defineProps<{ item: FlowRun }>()

const start = computed(() => {
  return new Date(props.item.start_time)
})

const end = computed(() => {
  if (!props.item.end_time) {
    const date = new Date()
    date.setMinutes(date.getMinutes() + 1)
    return date
  }

  return new Date(props.item.end_time)
})

const flow_runs_filter_body: TaskRunsFilter = {
  sort: 'START_TIME_DESC',
  flow_runs: {
    id: {
      any_: [props.item.id]
    }
  },
  task_runs: {
    subflow_runs: {
      exists_: false
    }
  }
}

const flow_filter_body: FlowsFilter = {
  flow_runs: {
    id: {
      any_: [props.item.id]
    }
  }
}

const taskRunHistoryFilter = computed(() => {
  const interval = Math.floor(
    Math.max(1, (end.value.getTime() - start.value.getTime()) / 1000 / 20)
  )
  return {
    history_start: start.value.toISOString(),
    history_end: end.value.toISOString(),
    history_interval_seconds: interval,
    flow_runs: flow_runs_filter_body.flow_runs
  }
})

const queries: { [key: string]: Query } = {
  task_run_history: Api.query({
    endpoint: Endpoints.task_runs_history,
    body: taskRunHistoryFilter
  }),
  task_run_count: Api.query({
    endpoint: Endpoints.task_runs_count,
    body: flow_runs_filter_body
  }),
  flow: Api.query({
    endpoint: Endpoints.flows,
    body: flow_filter_body
  })
}

const duration = computed(() => {
  return state.value == 'pending' || state.value == 'scheduled'
    ? '--'
    : props.item.total_run_time
    ? secondsToApproximateString(props.item.total_run_time)
    : secondsToApproximateString(props.item.estimated_run_time)
})

const state = computed(() => {
  return props.item.state.type.toLowerCase()
})

const tags = computed(() => {
  return props.item.tags
})

const flow = computed(() => {
  return queries.flow?.response?.value?.[0] || {}
})

const taskRunCount = computed((): number => {
  return queries.task_run_count?.response?.value || 0
})

const taskRunHistory = computed((): Buckets => {
  return queries.task_run_history?.response.value || []
})
</script>

<style lang="scss" scoped></style>

<style lang="scss" scoped>
@use '@/styles/components/list-item--flow-run.scss';
</style>
