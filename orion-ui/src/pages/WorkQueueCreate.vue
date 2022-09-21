<template>
  <p-layout-default>
    <template #header>
      <PageHeadingWorkQueueCreate />
    </template>

    <WorkQueueCreateForm action="Create" @submit="createQueue" @cancel="goToQueues" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { WorkQueueCreateForm, PageHeadingWorkQueueCreate, WorkQueueCreate } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const router = useRouter()

  const goToQueues = (): void => {
    router.push(routes.workQueues())
  }

  const createQueue = async (workQueue: WorkQueueCreate): Promise<void> => {
    try {
      const { id } = await workQueuesApi.createWorkQueue(workQueue)
      showToast('Work queue has been created', 'success')
      router.push(routes.workQueue(id))
    } catch (error) {
      showToast('Error occurred while creating new work queue', 'error')
      console.error(error)
    }
  }

  usePageTitle('Create Work Queue')
</script>