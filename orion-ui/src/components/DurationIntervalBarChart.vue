<template>
  <IntervalBarChartCard
    title="Total Duration"
    height="77px"
    v-bind="{ items, filter }"
  >
    <template v-slot:total="{ total }">
      <div class="font--secondary">
        {{ secondsToApproximateString(total) }}
      </div>
    </template>
    <template v-slot:popover-header>
      <div class="interval-bar-chart-card__popover-header">
        <i
          class="
            interval-bar-chart-card__popover-icon
            pi pi-bar-chart-box-line pi-1
            mr-1
          "
        />
        <span>Flow Run Duration</span>
      </div>
    </template>

    <template v-slot:popover-content="item">
      <table class="interval-bar-chart-item__table">
        <tr>
          <td>Start Time:</td>
          <td>
            {{ formatDateTimeNumeric(item.interval_start) }}
          </td>
        </tr>
        <tr>
          <td>End Time:</td>
          <td>
            {{ formatDateTimeNumeric(item.interval_end) }}
          </td>
        </tr>
        <tr>
          <td>Flow Runs:</td>
          <td>{{ countFlowsInStates(item.data.states) }}</td>
        </tr>
        <tr>
          <td>Run Time:</td>
          <td>
            {{ secondsToApproximateString(item.value) }}
            ({{ percentOfTotalSeconds(item.value) }})
          </td>
        </tr>
      </table>
    </template>
  </IntervalBarChartCard>
</template>

<script lang="ts" setup>
import { computed, defineProps } from 'vue'
import { Api, Endpoints, FlowRunsHistoryFilter } from '@/plugins/api'
import IntervalBarChartCard from './IntervalBarChart/IntervalBarChartCard.vue'
import { IntervalBarChartItem } from './IntervalBarChart/Types/IntervalBarChartItem'
import { Bucket, StateBucket } from '@/typings/run_history'
import { formatDateTimeNumeric } from '@/utilities/date'
import { secondsToApproximateString } from '@/util/util'

const props = defineProps<{
  filter: FlowRunsHistoryFilter
}>()

const filter = computed(() => {
  return props.filter
})

const queries = {
  query: Api.query({
    endpoint: Endpoints.flow_runs_history,
    body: filter,
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
    (acc, curr) => acc + curr.sum_estimated_run_time,
    0
  )
})

const items = computed<IntervalBarChartItem<Bucket>[]>(() => {
  const buckets: Bucket[] = queries.query.response.value || []
  const items = buckets.map(bucketToChartItem)
  const filteredItems = items.filter((item) => item.value)

  return filteredItems
})

const totalSeconds = computed<number>((): number => {
  return items.value.reduce((acc, curr) => acc + curr.value, 0)
})

const percentOfTotalSeconds = (value: number): `${number}%` => {
  const percent = (value / totalSeconds.value) * 100

  return `${Math.round(percent)}%`
}

const countFlowsInStates = (states: StateBucket[]): number => {
  return states.reduce((acc, cur) => cur.count_runs, 0)
}
</script>

<style lang="scss">
@use '@/styles/abstracts/variables';

.interval-bar-chart-card__popover-icon {
  color: $grey-40;
}
</style>
