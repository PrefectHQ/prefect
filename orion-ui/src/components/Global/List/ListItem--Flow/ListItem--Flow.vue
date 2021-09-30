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
        {{ flowRunCount }} flow run{{ flowRunCount == 1 ? '' : 's' }}
      </rounded-button>

      <rounded-button class="mr-1">
        {{ taskRunCount }} task run{{ taskRunCount == 1 ? '' : 's' }}
      </rounded-button>
    </div>

    <div v-breakpoints="'md'" class="chart-container">
      <RunHistoryChart
        :items="flowRunHistory"
        :interval-start="store.getters.globalFilter.start"
        :interval-end="store.getters.globalFilter.end"
        :interval-seconds="store.getters.globalFilter.intervalSeconds"
        :padding="{ top: 3, bottom: 3, left: 3, right: 3, middle: 2 }"
      />
    </div>
  </list-item>
</template>

<script lang="ts" setup>
import { defineProps, computed } from 'vue'
import RunHistoryChart from '@/components/RunHistoryChart/RunHistoryChart--Chart.vue'
import { Api, Query, Endpoints, FlowsFilter } from '@/plugins/api'
import { Flow } from '@/typings/objects'
import { Buckets } from '@/typings/run_history'
import { useStore } from 'vuex'

const store = useStore()
const props = defineProps<{ item: Flow }>()

const flows: FlowsFilter = {
  flows: {
    id: {
      any_: [props.item.id]
    }
  }
}

const flowRunHistoryFilter = computed(() => {
  return {
    history_start: store.getters.globalFilter.start.toISOString(),
    history_end: store.getters.globalFilter.end.toISOString(),
    history_interval_seconds: store.getters.globalFilter.intervalSeconds * 4,
    flows: flows.flows
  }
})

const queries: { [key: string]: Query } = {
  flow_run_history: Api.query({
    endpoint: Endpoints.flow_runs_history,
    body: flowRunHistoryFilter
  }),
  flow_run_count: Api.query({
    endpoint: Endpoints.flow_runs_count,
    body: flows
  }),
  task_run_count: Api.query({
    endpoint: Endpoints.task_runs_count,
    body: flows
  })
}

const flowRunCount = computed((): number => {
  return queries.flow_run_count.response || 0
})

const taskRunCount = computed((): number => {
  return queries.task_run_count.response || 0
})

const flowRunHistory = computed((): Buckets => {
  return queries.flow_run_history?.response.value || []
})
</script>

<style lang="scss" scoped>
@use '@/styles/components/list-item--flow.scss';
</style>
