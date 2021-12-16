<template>
  <Card shadow="sm" class="interval-bar-chart-card">
    <template v-slot:header>
      <div class="interval-bar-chart-card__header">
        <div class="subheader">{{ props.title }}</div>
        <template v-if="items.length">
          <slot name="total" :total="total">
            <div class="font--secondary">
              {{ total }}
            </div>
          </slot>
        </template>
      </div>
    </template>

    <div class="px-2 pb-2" :style="{ height }">
      <IntervalBarChart v-bind="{ items, intervalStart, intervalEnd }">
        <template v-slot:popover-header="item">
          <slot name="popover-header" v-bind="{ item, total }" />
        </template>
        <template v-slot:popover-content="item">
          <slot name="popover-content" v-bind="{ item, total }" />
        </template>
      </IntervalBarChart>
    </div>
  </Card>
</template>
<script lang="ts" setup>
import { computed } from 'vue'
import IntervalBarChart from './IntervalBarChart.vue'
import { IntervalBarChartItem } from './Types/IntervalBarChartItem'
import { FlowRunsHistoryFilter } from '@/plugins/api'

const props = defineProps<{
  filter: FlowRunsHistoryFilter
  title: string
  height: string
  items: IntervalBarChartItem[]
}>()

const intervalStart = computed(() => {
  return new Date(props.filter.history_start)
})

const intervalEnd = computed(() => {
  return new Date(props.filter.history_end)
})

const total = computed<number>(() => {
  return props.items.reduce((total, item) => total + item.value, 0)
})
</script>

<style lang="scss">
.interval-bar-chart-card__header {
  padding: var(--p-1) var(--p-2);
  display: flex;
  justify-content: space-between;
}

.interval-bar-chart-card__popover-header {
  display: flex;
  align-items: center;
}
</style>
