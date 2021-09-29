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
        show-axis
      />
      <div v-else class="font--secondary subheader no-data"> -- </div>
    </div>
  </Card>
</template>

<script lang="ts" setup>
import RunHistoryChart from './RunHistoryChart.vue'
import { Api, FlowRunsHistoryFilter, Query, Endpoints } from '@/plugins/api'
import { defineProps, computed } from 'vue'

const props = defineProps<{ filter: FlowRunsHistoryFilter }>()

const queries: { [key: string]: Query } = {
  flow_run_history: Api.query(Endpoints.flow_runs_history, props.filter, {})
}

const buckets = computed(() => {
  console.log(queries.flow_run_history.response.value)
  return queries.flow_run_history.response.value || []
})
</script>

<style lang="scss">
@use '@/styles/components/run-history--card.scss';
</style>
