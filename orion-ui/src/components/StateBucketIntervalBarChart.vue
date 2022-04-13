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
  import { FlowRunsHistoryFilter, KeysMatching, RunHistory, StateHistory } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import IntervalBarChartCard from './IntervalBarChart/IntervalBarChartCard.vue'
  import { IntervalBarChartItem } from './IntervalBarChart/Types/IntervalBarChartItem'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { secondsToApproximateString } from '@/util/util'

  const props = defineProps<{
    title: string,
    filter: FlowRunsHistoryFilter,
    property: KeysMatching<StateHistory, number>,
  }>()

  const history = useSubscription(flowRunsApi.getFlowRunsHistory, [props.filter], {
    interval: 30000,
  })

  const historyToChartItem = (
    bucket: RunHistory,
  ): IntervalBarChartItem<RunHistory> => ({
    data: bucket,
    interval_start: bucket.intervalStart,
    interval_end: bucket.intervalEnd,
    value: bucket.states.reduce((acc, curr) => acc + curr[props.property], 0),
  })

  const items = computed<IntervalBarChartItem<RunHistory>[]>(() => {
    const buckets: RunHistory[] = history.response ?? []
    const items = buckets.map(historyToChartItem)
    const filteredItems = items.filter((item) => item.value)

    return filteredItems
  })

  const average = (total: number): string => {
    const avg = total / items.value.length

    return secondsToApproximateString(avg)
  }

  const countRunsInStates = (states: StateHistory[]): number => {
    return states.reduce((total, state) => total + state.countRuns, 0)
  }
</script>
