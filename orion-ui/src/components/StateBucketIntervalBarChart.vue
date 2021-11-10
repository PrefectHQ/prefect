<template>
  <IntervalBarChartCard height="77px" v-bind="{ title, items, filter }">
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
        <slot name="popover-header" />
      </div>
    </template>

    <template v-slot:popover-content="scope">
      <slot name="popover-content" v-bind="scope" />
    </template>
  </IntervalBarChartCard>
</template>

<script lang="ts" setup>
import { computed, defineProps } from 'vue'
import { Api, Endpoints, FlowRunsHistoryFilter } from '@/plugins/api'
import IntervalBarChartCard from './IntervalBarChart/IntervalBarChartCard.vue'
import { IntervalBarChartItem } from './IntervalBarChart/Types/IntervalBarChartItem'
import { Bucket, StateBucket } from '@/typings/run_history'
import { secondsToApproximateString } from '@/util/util'
import { KeysMatching } from '@/types/utilities'

const props = defineProps<{
  title: string
  filter: FlowRunsHistoryFilter // todo: this should come from the store
  property: KeysMatching<StateBucket, number>
}>()

const filter = computed(() => {
  return props.filter
})

// todo: this query is being run once for each chart.
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
  value: bucket.states.reduce((acc, curr) => acc + curr[props.property], 0)
})

const items = computed<IntervalBarChartItem<Bucket>[]>(() => {
  const buckets: Bucket[] = queries.query.response.value || []
  const items = buckets.map(bucketToChartItem)
  const filteredItems = items.filter((item) => item.value)

  return filteredItems
})
</script>

<style lang="scss">
@use '@/styles/abstracts/variables';

.interval-bar-chart-card__popover-icon {
  color: $grey-40;
}
</style>
