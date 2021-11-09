<template>
  <Card shadow="sm" class="interval-bar-chart-card">
    <template v-slot:header>
      <div class="interval-bar-chard-card__header">
        <div class="subheader">{{ props.title }}</div>
        <template v-if="items.length">
          <div class="font--secondary">
            {{ secondsToApproximateString(totalSeconds) }}
          </div>
        </template>
      </div>
    </template>

    <div class="px-2 pb-2" :style="{ height: height }">
      <IntervalBarChart
        v-if="items && items.length"
        :items="items"
        :interval-seconds="intervalSeconds"
        :interval-start="intervalStart"
        :interval-end="intervalEnd"
      />
      <div v-else class="font--secondary subheader no-data"> -- </div>
    </div>
  </Card>
</template>
<script lang="ts" setup>
import IntervalBarChart from './IntervalBarChart.vue'
import { Api, FlowRunsHistoryFilter, Query, Endpoints } from '@/plugins/api'
import { defineProps, computed } from 'vue'
import { Bucket, StateBucket } from '@/typings/run_history'
import { secondsToApproximateString } from '@/util/util'
import { IntervalBarChartItem } from './Types/IntervalBarChartItem'

const props = defineProps<{
  endpoint: string
  filter: FlowRunsHistoryFilter
  title: string
  stateBucketKey: keyof StateBucket
  height: string
}>()

const queries: { [key: string]: Query } = {
  query: Api.query({
    endpoint: Endpoints[props.endpoint],
    body: props.filter,
    options: {
      pollInterval: 30000
    }
  })
}

const buckets = computed<Bucket[]>(() => {
  return queries.query.response.value || []
})

const intervalStart = computed(() => {
  return new Date(props.filter.history_start)
})

const intervalEnd = computed(() => {
  return new Date(props.filter.history_end)
})

const intervalSeconds = computed(() => {
  return props.filter.history_interval_seconds
})

const items = computed<IntervalBarChartItem<Bucket>[]>(() => {
  return buckets.value.map((item) => {
    return {
      data: item,
      interval_start: item.interval_start,
      interval_end: item.interval_end,
      value: item.states.reduce(
        (acc, curr) => acc + (curr[props.stateBucketKey] as number),
        0
      )
    }
  })
})

const totalSeconds = computed<number>(() => {
  return items.value.reduce((total, item) => {
    return (total += item.value)
  }, 0)
})
</script>

<style lang="scss">
.interval-bar-chard-card__header {
  padding: var(--p-1) var(--p-2);
  display: flex;
  justify-content: space-between;
}
</style>
