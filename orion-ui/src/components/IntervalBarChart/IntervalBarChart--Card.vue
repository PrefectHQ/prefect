<template>
  <Card shadow="sm">
    <template v-slot:aside>
      <div class="pl-2 pt-1" style="width: 100px">
        <div class="subheader">{{ props.title }}</div>
      </div>
    </template>
    <div class="chart px-1">
      <BarChart
        :items="items"
        :interval-seconds="intervalSeconds"
        :interval-start="intervalStart"
        :interval-end="intervalEnd"
        height="117px"
      />
    </div>
  </Card>
</template>

<script lang="ts" setup>
import BarChart from './IntervalBarChart--Chart.vue'
import { Api, FlowRunsHistoryFilter, Query, Endpoints } from '@/plugins/api'
import { defineProps, computed, watch } from 'vue'
import { Bucket, StateBucket } from '@/typings/run_history'

const props = defineProps<{
  endpoint: string
  filter: FlowRunsHistoryFilter
  title: string
  stateBucketKey: keyof StateBucket
}>()

const queries: { [key: string]: Query } = {
  query: Api.query({
    endpoint: Endpoints[props.endpoint],
    body: props.filter,
    options: {
      pollInterval: 10000
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

watch(
  () => props.filter,
  async () => {
    queries.query.body = props.filter
    queries.query.startPolling()
  }
)

const items = computed(() => {
  const calcedItems = (queries.query.response.value || []).map(
    (item: Bucket) => {
      return {
        interval_start: item.interval_start,
        interval_end: item.interval_end,
        value: item.states.reduce(
          (acc: number, curr: StateBucket) =>
            acc + (curr[props.stateBucketKey] as number),
          0
        )
      }
    }
  )

  console.log(queries.query.response.value, calcedItems)
  return calcedItems
})
</script>

<style lang="scss">
@use '@/styles/components/interval-bar-chart--card.scss';

.chart {
  height: 117px;
  overflow: hidden;
}
</style>
