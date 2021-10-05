<template>
  <Card shadow="sm">
    <template v-slot:header>
      <div class="subheader py-1 px-2">{{ props.title }}</div>
    </template>

    <div class="px-2 pb-2" :style="{ height: height }">
      <BarChart
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
import BarChart from './IntervalBarChart--Chart.vue'
import { Api, FlowRunsHistoryFilter, Query, Endpoints } from '@/plugins/api'
import { defineProps, computed } from 'vue'
import { Bucket, StateBucket } from '@/typings/run_history'

const props = defineProps<{
  endpoint: string
  filter: FlowRunsHistoryFilter
  title: string
  stateBucketKey: keyof StateBucket
  height: string
}>()

const filter = computed(() => {
  return props.filter
})

const queries: { [key: string]: Query } = {
  query: Api.query({
    endpoint: Endpoints[props.endpoint],
    body: filter,
    options: {
      pollInterval: 30000
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

const items = computed(() => {
  return (queries.query.response.value || []).map((item: Bucket) => {
    return {
      interval_start: item.interval_start,
      interval_end: item.interval_end,
      value: item.states.reduce(
        (acc: number, curr: StateBucket) =>
          acc + (curr[props.stateBucketKey] as number),
        0
      )
    }
  })
})
</script>

<style lang="scss" scoped>
@use '@/styles/components/interval-bar-chart--card.scss';
</style>
