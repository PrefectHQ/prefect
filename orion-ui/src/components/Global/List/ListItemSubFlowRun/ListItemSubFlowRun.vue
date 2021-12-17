<template>
  <ListItem class="list-item--flow-run d-flex align-start justify-start">
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
      <BreadCrumbs class="flex-grow-1" tag="h2" :crumbs="crumbs" />

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
      <ButtonRounded disabled>
        {{ taskRunCount }} task run{{ taskRunCount == 1 ? '' : 's' }}
      </ButtonRounded>
    </div>

    <div v-breakpoints="'md'" class="chart-container mr-2">
      <RunHistoryChart
        :items="taskRunHistory"
        :interval-start="start"
        :interval-end="end"
        :interval-seconds="store.getters.globalFilter.intervalSeconds"
        static-median
        :padding="{ top: 3, bottom: 3, left: 6, right: 6, middle: 2 }"
        disable-popovers
      />
    </div>

    <div class="font--secondary item--duration mr-2">
      {{ duration }}
    </div>

    <router-link :to="`/flow-run/${item.id}`" class="icon-link">
      <i class="pi pi-arrow-right-s-line" />
    </router-link>
  </ListItem>
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import { Api, Query, Endpoints, FlowRunsFilter } from '@/plugins/api'
import { TaskRun } from '@/typings/objects'
import { secondsToApproximateString } from '@/util/util'
import { Buckets } from '@/typings/run_history'
import { useStore } from 'vuex'
import RunHistoryChart from '@/components/RunHistoryChart/RunHistoryChart--Chart.vue'

const store = useStore()
const props = defineProps<{ item: TaskRun }>()

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

const flowRunFilterBody = computed<FlowRunsFilter>(() => {
  return {
    flow_runs: {
      id: {
        any_: [props.item.state.state_details.child_flow_run_id]
      }
    }
  }
})

const taskRunHistoryFilter = computed(() => {
  const interval = Math.floor(
    Math.max(1, (end.value.getTime() - start.value.getTime()) / 1000 / 5)
  )
  return {
    history_start: start.value.toISOString(),
    history_end: end.value.toISOString(),
    history_interval_seconds: interval,
    flow_runs: flowRunFilterBody.value.flow_runs
  }
})

const queries: { [key: string]: Query } = {
  flow_run: Api.query({
    endpoint: Endpoints.flow_runs,
    body: flowRunFilterBody.value
  }),
  flow: Api.query({
    endpoint: Endpoints.flows,
    body: flowRunFilterBody.value
  }),
  task_run_history: Api.query({
    endpoint: Endpoints.task_runs_history,
    body: taskRunHistoryFilter.value
  }),
  task_run_count: Api.query({
    endpoint: Endpoints.task_runs_count,
    body: flowRunFilterBody
  })
}

const state = computed(() => {
  return props.item.state.type.toLowerCase()
})

const tags = computed(() => {
  return props.item.tags
})

const flowRun = computed(() => {
  return queries.flow_run?.response?.value?.[0] || {}
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

const duration = computed(() => {
  return state.value == 'pending' || state.value == 'scheduled'
    ? '--'
    : props.item.total_run_time
    ? secondsToApproximateString(props.item.total_run_time)
    : secondsToApproximateString(props.item.estimated_run_time)
})

const crumbs = computed(() => {
  return [
    { text: flow.value?.name },
    { text: flowRun.value?.name, to: `/flow-run/${flowRun.value?.id}` },
    { text: props.item.name }
  ]
})
</script>

<style lang="scss" scoped>
@use '@/styles/components/list-item--flow-run.scss';
</style>
