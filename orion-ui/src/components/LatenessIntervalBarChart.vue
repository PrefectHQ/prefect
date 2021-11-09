<template>
  <IntervalBarChartCard
    title="Total Lateness"
    height="77px"
    v-bind="{ items, filter }"
  >
    <template v-slot:popover-header>
      <div class="interval-bar-chart-card__popover-header">
        <i class="pi pi-bar-chart-box-line pi-1 mr-1" />
        <span>Lateness</span>
      </div>
    </template>
  </IntervalBarChartCard>
</template>

<script lang="ts" setup>
import { computed, defineProps } from 'vue'
import { Api, Endpoints, FlowRunsHistoryFilter } from '@/plugins/api'
import IntervalBarChartCard from './IntervalBarChart/IntervalBarChartCard.vue'
import { IntervalBarChartItem } from './IntervalBarChart/Types/IntervalBarChartItem'
import { Bucket } from '@/typings/run_history'

const props = defineProps<{
  filter: FlowRunsHistoryFilter
}>()

const queries = {
  query: Api.query({
    endpoint: Endpoints.flow_runs_history,
    body: props.filter,
    options: {
      pollInterval: 30000
    }
  })
}

const bucketToChartItem = (bucket: Bucket): IntervalBarChartItem<Bucket> => ({
  data: bucket,
  interval_start: bucket.interval_start,
  interval_end: bucket.interval_end,
  value: bucket.states.reduce(
    (acc, curr) => acc + curr.sum_estimated_lateness + 1, // remove the 1
    0
  )
})

const items = computed<IntervalBarChartItem<Bucket>[]>(() => {
  const buckets: Bucket[] = queries.query.response.value || []
  const items = buckets.map(bucketToChartItem)
  const filteredItems = items.filter((item) => item.value)

  return filteredItems
})
</script>
