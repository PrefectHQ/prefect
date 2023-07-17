<template>
  <div class="flow-stats">
    <div class="flow-stats__cards">
      <FlowRunHistoryCard :filter="flowRunsFilter" />
      <CumulativeTaskRunsCard :filter="taskRunsFilter" />
    </div>
    <TimeSpanFilter v-model:selected="timeSpanInSeconds" size="sm" />
  </div>
</template>

<script lang="ts" setup>
  import {
    CumulativeTaskRunsCard,
    TimeSpanFilter,
    FlowRunHistoryCard,
    subscriptionIntervalKey,
    mapper
  } from '@prefecthq/prefect-ui-library'
  import { NumberRouteParam, useRouteQueryParam } from '@prefecthq/vue-compositions'
  import { secondsInHour, secondsToMilliseconds } from 'date-fns'
  import { computed, provide, toRefs } from 'vue'

  const props = defineProps<{
    flowId: string,
  }>()

  const { flowId } = toRefs(props)
  const timeSpanInSeconds = useRouteQueryParam('span', NumberRouteParam, secondsInHour * 24)
  const flowStats = computed(() => ({
    flowId: flowId.value,
    timeSpanInSeconds: timeSpanInSeconds.value,
  }))

  provide(subscriptionIntervalKey, {
    interval: secondsToMilliseconds(30),
  })

  const flowRunsFilter = computed(() => mapper.map('FlowStatsFilter', flowStats.value, 'FlowRunsFilter'))
  const taskRunsFilter = computed(() => mapper.map('FlowStatsFilter', flowStats.value, 'TaskRunsFilter'))
</script>

<style>
.flow-stats { @apply
  w-full
  flex
  flex-col
  gap-4
  items-center
}

.flow-stats__cards { @apply
  w-full
  grid
  gap-5
  sm:grid-cols-2
}
</style>