<template>
  <div class="flow-stats">
    <div class="flow-stats__cards">
      <FlowRunHistoryCard :filter="flowRunsFilter" />
      <CumulativeTaskRunsCard :filter="taskRunsFilter" />
    </div>
    <DateRangeSelect v-model="filter.range" small />
  </div>
</template>

<script lang="ts" setup>
  import {
    CumulativeTaskRunsCard,
    FlowRunHistoryCard,
    subscriptionIntervalKey,
    mapper,
    useWorkspaceDashboardFilterFromRoute,
    DateRangeSelect
  } from '@prefecthq/prefect-ui-library'
  import { secondsInDay, secondsToMilliseconds } from 'date-fns'
  import { computed, provide, toRefs } from 'vue'

  const props = defineProps<{
    flowId: string,
  }>()

  const { flowId } = toRefs(props)

  const filter = useWorkspaceDashboardFilterFromRoute({
    range: { type: 'span', seconds: -secondsInDay },
    tags: [],
  })

  const flowStats = computed(() => ({
    flowId: flowId.value,
    range: filter.range,
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