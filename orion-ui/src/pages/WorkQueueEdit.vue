<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkQueueEdit :work-queue="workQueueDetails" />
    </template>

    <WorkQueueEditForm :work-queue="workQueueDetails" @submit="updateQueue" @cancel="goBack" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { WorkQueueEditForm, PageHeadingWorkQueueEdit, WorkQueueEdit, useWorkspaceApi } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import router from '@/router'

  const api = useWorkspaceApi()
  const workQueueId = useRouteParam('workQueueId')

  const workQueueDetails = await api.workQueues.getWorkQueue(workQueueId.value)

  const goBack = (): void => {
    router.back()
  }

  const updateQueue = async (workQueue: WorkQueueEdit): Promise<void> => {
    try {
      await api.workQueues.updateWorkQueue(workQueueId.value, workQueue)
      showToast(`${workQueueDetails.name} updated`, 'success')
      goBack()
    } catch (error) {
      showToast('Error occurred while updating your queue', 'error')
      console.error(error)
    }
  }

  usePageTitle(`Edit Work Queue: ${workQueueDetails.name}`)
</script>