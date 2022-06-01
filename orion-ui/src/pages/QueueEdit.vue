<template>
  <p-layout-default class="queue-create">
    <p class="text-xl font-bold">
      Edit Work Queue
    </p>
    <p class="text-base text-gray-500">
      Fill out the details below.
    </p>

    <WorkQueueForm :work-queue="workQueueDetails" @submit="submit" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { WorkQueueForm, useRouteParam, WorkQueue } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const workQueueId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }

  const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId.value], subscriptionOptions)
  const workQueueDetails = computed(() => workQueueSubscription.response)

  const submit = (workQueue: Partial<WorkQueue>): void => {
    console.log('submitted', workQueue)
  }
</script>