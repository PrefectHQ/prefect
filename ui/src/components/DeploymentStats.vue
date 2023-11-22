<template>
    <div class="deployment-stats">
      <div class="deployment-stats__cards">
        <FlowRunHistoryCard :filter="flowRunsFilter" />
        <CumulativeTaskRunsCard :filter="taskRunsFilter" />
      </div>
      <TimeSpanFilter v-model:selected="timeSpanInSeconds" small />
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
      deploymentId: string,
    }>()
  
    const { deploymentId } = toRefs(props)
    const timeSpanInSeconds = useRouteQueryParam('span', NumberRouteParam, secondsInHour * 24)
    const deploymentStats = computed(() => ({
      deploymentId: deploymentId.value,
      timeSpanInSeconds: timeSpanInSeconds.value,
    }))
  
    provide(subscriptionIntervalKey, {
      interval: secondsToMilliseconds(30),
    })
  
    const flowRunsFilter = computed(() => mapper.map('FlowStatsFilter', deploymentStats.value, 'FlowRunsFilter'))
    const taskRunsFilter = computed(() => mapper.map('FlowStatsFilter', deploymentStats.value, 'TaskRunsFilter'))
  </script>
  
  <style>
  .deployment-stats { @apply
    w-full
    flex
    flex-col
    gap-4
    items-center
  }
  
  .deployment-stats__cards { @apply
    w-full
    grid
    gap-5
    sm:grid-cols-2
  }
  </style>