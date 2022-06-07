<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkQueueEdit />
    </template>

    <WorkQueueForm :work-queue="workQueueDetails" @submit="updateQueue" @cancel="goBack" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { WorkQueueForm, useRouteParam, PageHeadingWorkQueueEdit, IWorkQueueRequest } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import router from '@/router'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const workQueueId = useRouteParam('id')

  const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId.value])
  const { response:workQueueDetails } = await workQueueSubscription.promise()

  const goBack = (): void => {
    router.back()
  }

  const updateQueue = async (workQueue: IWorkQueueRequest): Promise<void> => {
    try {
      await workQueuesApi.updateWorkQueue(workQueueId.value, workQueue)
      showToast(`${workQueueDetails!.name} updated`, 'success', undefined, 3000)
      goBack()
    } catch (error) {
      showToast('Error occurred while updating your queue', 'error', undefined, 3000)
      console.error(error)
    }
  }
</script>