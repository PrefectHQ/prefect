<template>
  <p-layout-default class="queue-create">
    <p class="text-xl font-bold">
      Edit Work Queue
    </p>
    <p class="text-base text-gray-500">
      Fill out the details below.
    </p>

    <WorkQueueForm :work-queue="workQueueDetails" @submit="updateQueue" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { WorkQueueForm, useRouteParam } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const workQueueId = useRouteParam('id')

  const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId.value])
  const workQueueDetails = computed(() => workQueueSubscription.response)

  const updateQueue = async (workQueue: any): Promise<void> => {
    try {
      await workQueuesApi.updateWorkQueue(workQueueId.value, workQueue)
      showToast(`Work queue ${workQueueDetails.value?.name} has been updated`, 'success', undefined, 3000)
    } catch (error) {
      showToast('Error occurred while updating your queue', 'error', undefined, 3000)
      console.error(error)
    }
  }
</script>