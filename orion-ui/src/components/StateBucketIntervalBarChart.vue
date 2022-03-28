<template>
  <IntervalBarChartCard height="77px" v-bind="{ title, items, filter }">
    <template #total="{ total }">
      <div class="font--secondary">
        {{ average(total) }}
        <span class="caption-small">AVG</span>
      </div>
    </template>
    <template #popover-header>
      <div class="interval-bar-chart-card__popover-header">
        <i class="pi pi-bar-chart-box-line pi-1 mr-1 text--grey-40" />
        <slot name="popover-header" />
      </div>
    </template>

    <template #popover-content="scope">
      <slot
        name="popover-content"
        v-bind="scope"
        :runs="countRunsInStates(scope.item.data.states)"
      />
    </template>
  </IntervalBarChartCard>
</template>

<script lang="ts" setup>
  import { FlowRunsHistoryFilter } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import IntervalBarChartCard from './IntervalBarChart/IntervalBarChartCard.vue'
  import { IntervalBarChartItem } from './IntervalBarChart/Types/IntervalBarChartItem'
  import FlowRunHistory from '@/models/flowRunHistory'
  import FlowRunStateHistory from '@/models/flowRunStateHistory'
  import FlowRunsApi from '@/services/flowRunsApi'
  import { KeysMatching } from '@/types/utilities'
  import { secondsToApproximateString } from '@/util/util'

  const props = defineProps<{
    title: string,
    filter: FlowRunsHistoryFilter, // todo: this should come from the store
    property: KeysMatching<FlowRunStateHistory, number>,
  }>()

  const history = useSubscription(FlowRunsApi.History, [props.filter], {
    interval: 30000,
  })

  const historyToChartItem = (
    bucket: FlowRunHistory,
  ): IntervalBarChartItem<FlowRunHistory> => ({
    data: bucket,
    interval_start: bucket.interval_start,
    interval_end: bucket.interval_end,
    value: bucket.states.reduce((acc, curr) => acc + curr[props.property], 0),
  })

  const items = computed<IntervalBarChartItem<FlowRunHistory>[]>(() => {
    const buckets: FlowRunHistory[] = history.response || []
    const items = buckets.map(historyToChartItem)
    const filteredItems = items.filter((item) => item.value)

    return filteredItems
  })

  const average = (total: number): string => {
    const avg = total / items.value.length

    return secondsToApproximateString(avg)
  }

  const countRunsInStates = (states: FlowRunStateHistory[]): number => {
    return states.reduce((total, state) => total + state.count_runs, 0)
  }
</script>
