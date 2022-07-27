<template>
  <p-layout-default class="work-queue">
    <template #header>
      <PageHeadingWorkQueue
        v-if="workQueue"
        :queue="workQueue"
        @update="workQueueSubscription.refresh"
        @delete="routeToQueues"
      />
    </template>

    <p-layout-well class="work-queue__body">
      <template #header>
        <CodeBanner :command="workQueueCliCommand" title="Work queue is ready to go!" subtitle="Work queues define the work to be done and agents poll a specific work queue for new work." />
      </template>

      <p-tabs :tabs="tabs">
        <template #details>
          <WorkQueueDetails v-if="workQueue" :work-queue="workQueue" />
        </template>
        <template #upcoming-runs>
          <WorkQueueFlowRunsList v-if="workQueue" :work-queue="workQueue" />
        </template>
      </p-tabs>

      <template #well>
        <WorkQueueDetails v-if="workQueue" :work-queue="workQueue" />
      </template>
    </p-layout-well>
  </p-layout-default>
</template>


<script lang="ts" setup>
  import { WorkQueueDetails, PageHeadingWorkQueue, WorkQueueFlowRunsList, CodeBanner } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const router = useRouter()

  const tabs = computed(() => {
    const values = ['Upcoming Runs']

    if (!media.xl) {
      values.unshift('Details')
    }

    return values
  })

  const workQueueId = useRouteParam('id')
  const workQueueCliCommand = computed(() => `prefect agent start ${workQueueId.value}`)

  const subscriptionOptions = {
    interval: 300000,
  }

  const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId.value], subscriptionOptions)
  const workQueue = computed(() => workQueueSubscription.response)

  const routeToQueues = (): void => {
    router.push(routes.workQueues())
  }
</script>

<style>
/* This is an override since this is using nested layouts */
.work-queue__body {
  @apply
  p-0
}
</style>