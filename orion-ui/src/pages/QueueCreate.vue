<template>
  <p-layout-default>
    <template #header>
      <PageHeading :crumbs="header" />
    </template>

    <WorkQueueForm @submit="createQueue" @cancel="goToQueues" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { WorkQueueForm, PageHeading } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import router, { routes } from '@/router'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const header = [{ text: 'Create Work Queue' }]

  const goToQueues = (): void => {
    router.push(routes.queues())
  }

  const createQueue = async (workQueue: any): Promise<void> => {
    try {
      await workQueuesApi.createWorkQueue(workQueue)
      showToast('Work queue has been created', 'success', undefined, 3000)
      goToQueues()
    } catch (error) {
      showToast('Error occurred while creating new queue', 'error', undefined, 3000)
      console.error(error)
    }
  }
</script>