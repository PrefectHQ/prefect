<template>
  <StateBucketIntervalBarChart
    title="Run Time"
    property="sumEstimatedRunTime"
    v-bind="{ filter }"
  >
    <template #popover-header>
      <span>Run time</span>
    </template>

    <template #popover-content="{ item, runs }">
      <table class="table table--data">
        <tr>
          <td>Run count:</td>
          <td>{{ runs }}</td>
        </tr>
        <tr>
          <td>Run time:</td>
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
  import { FlowRunsHistoryFilter } from '@prefecthq/orion-design'
  import { computed } from 'vue'
  import StateBucketIntervalBarChart from './StateBucketIntervalBarChart.vue'
  import { secondsToApproximateString } from '@/util/util'
  import { formatDateTimeNumeric } from '@/utilities/dates'

  const props = defineProps<{
    filter: FlowRunsHistoryFilter,
  }>()

  const filter = computed(() => {
    return props.filter
  })
</script>
