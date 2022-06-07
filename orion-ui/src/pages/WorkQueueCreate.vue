<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkQueueCreate />
    </template>

    <WorkQueueForm @submit="createQueue" @cancel="goToQueues" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { WorkQueueForm, PageHeadingWorkQueueCreate, IWorkQueueRequest } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const router = useRouter()

  const goToQueues = (): void => {
    router.push(routes.workQueues())
  }

  const createQueue = async (workQueue: IWorkQueueRequest): Promise<void> => {
    try {
      const { id } = await workQueuesApi.createWorkQueue(workQueue)
      showToast('Work queue has been created', 'success')
      router.push(routes.workQueue(id))
    } catch (error) {
      showToast('Error occurred while creating new work queue', 'error')
      console.error(error)
    }
  }
</script>