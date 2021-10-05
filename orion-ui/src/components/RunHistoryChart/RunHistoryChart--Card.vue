<template>
  <Card shadow="sm">
    <template v-slot:header>
      <div class="subheader py-1 px-2">Run History</div>
    </template>

    <div class="px-2 pb-1 flex-grow-1">
      <RunHistoryChart
        v-if="buckets && buckets.length"
        :items="buckets"
        background-color="blue-5"
        :interval-seconds="intervalSeconds"
        :interval-start="intervalStart"
        :interval-end="intervalEnd"
        show-axis
      />
      <div v-else class="font--secondary subheader no-data"> -- </div>
    </div>
  </Card>
</template>

<script lang="ts" setup>
import RunHistoryChart from './RunHistoryChart--Chart.vue'
import { Api, FlowRunsHistoryFilter, Query, Endpoints } from '@/plugins/api'
import { defineProps, computed } from 'vue'

const props = defineProps<{ filter: FlowRunsHistoryFilter }>()

const filter = computed(() => {
  return props.filter
})

const queries: { [key: string]: Query } = {
  flow_run_history: Api.query({
    endpoint: Endpoints.flow_runs_history,
    body: filter.value,
    options: {
      pollInterval: 5000
    }
  })
}

const intervalStart = computed(() => {
  return new Date(props.filter.history_start)
})

const intervalEnd = computed(() => {
  return new Date(props.filter.history_end)
})

const intervalSeconds = computed(() => {
  return props.filter.history_interval_seconds
})

const buckets = computed(() => {
  return queries.flow_run_history.response.value || []
})
</script>

<style lang="scss" scoped>
@use '@/styles/components/run-history--card.scss';
</style>
