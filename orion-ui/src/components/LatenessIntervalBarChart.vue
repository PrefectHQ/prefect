<template>
  <StateBucketIntervalBarChart
    title="Lateness"
    property="sum_estimated_lateness"
    v-bind="{ filter }"
  >
    <template v-slot:popover-header>
      <span>Flow Run Lateness</span>
    </template>

    <template v-slot:popover-content="{ item, runs }">
      <table class="table table--data">
        <tr>
          <td>Run count:</td>
          <td>{{ runs }}</td>
        </tr>
        <tr>
          <td>Late by:</td>
          <td>
            {{ secondsToApproximateString(item.value) }}
          </td>
        </tr>
        <tr>
          <td>Started after:</td>
          <td>
            {{ formatDateTimeNumeric(item.interval_start) }}
          </td>
        </tr>
        <tr>
          <td>Started before:</td>
          <td>
            {{ formatDateTimeNumeric(item.interval_end) }}
          </td>
        </tr>
      </table>
    </template>
  </StateBucketIntervalBarChart>
</template>

<script lang="ts" setup>
import { computed, defineProps } from 'vue'
import { FlowRunsHistoryFilter } from '@/plugins/api'
import { formatDateTimeNumeric } from '@/utilities/dates'
import { secondsToApproximateString } from '@/util/util'
import StateBucketIntervalBarChart from './StateBucketIntervalBarChart.vue'

const props = defineProps<{
  filter: FlowRunsHistoryFilter
}>()

const filter = computed(() => {
  return props.filter
})
</script>
