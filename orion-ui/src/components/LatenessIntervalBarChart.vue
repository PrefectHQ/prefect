<template>
  <StateBucketIntervalBarChart
    title="Lateness"
    property="sum_estimated_lateness"
    v-bind="{ filter }"
  >
    <template v-slot:popover-header>
      <span>Flow Run Lateness</span>
    </template>

    <template v-slot:popover-content="{ item, total, flows }">
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
          <td>{{ flows }}</td>
        </tr>
        <tr>
          <td>Lateness:</td>
          <td>
            {{ secondsToApproximateString(item.value) }}
            ({{ calculatePercent(item.value, total) }})
          </td>
        </tr>
      </table>
    </template>
  </StateBucketIntervalBarChart>
</template>

<script lang="ts" setup>
import { computed, defineProps } from 'vue'
import { FlowRunsHistoryFilter } from '@/plugins/api'
import { formatDateTimeNumeric } from '@/utilities/date'
import { secondsToApproximateString } from '@/util/util'
import StateBucketIntervalBarChart from './StateBucketIntervalBarChart.vue'
import { calculatePercent } from '@/utilities/percent'

const props = defineProps<{
  filter: FlowRunsHistoryFilter
}>()

const filter = computed(() => {
  return props.filter
})
</script>

<style lang="scss">
@use '@/styles/abstracts/variables';

.interval-bar-chart-card__popover-icon {
  color: $grey-40;
}
</style>
