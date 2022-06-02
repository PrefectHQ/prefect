<template>
  <p-layout-default>
    <template #header>
      <PageHeading :crumbs="header" />
    </template>

    <WorkQueueForm :work-queue="workQueueDetails" @submit="updateQueue" @cancel="goToQueues" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { WorkQueueForm, useRouteParam, PageHeading } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import router from '@/router'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const header = [{ text: 'Edit Queue' }]

  const workQueueId = useRouteParam('id')

  const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId.value])
  const workQueueDetails = computed(() => workQueueSubscription.response)

  const goToQueues = (): void => {
    router.back()
  }

  const updateQueue = async (workQueue: any): Promise<void> => {
    try {
      await workQueuesApi.updateWorkQueue(workQueueId.value, workQueue)
      showToast(`${workQueueDetails.value?.name} updated`, 'success', undefined, 3000)
      goToQueues()
    } catch (error) {
      showToast('Error occurred while updating your queue', 'error', undefined, 3000)
      console.error(error)
    }
  }
</script>