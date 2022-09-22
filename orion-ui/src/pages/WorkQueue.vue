<template>
  <p-layout-default class="work-queue">
    <template #header>
      <PageHeadingWorkQueue
        v-if="workQueue"
        :work-queue="workQueue"
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

        <template #runs>
          <FlowRunList v-if="flowRuns.length" :flow-runs="flowRuns" disabled :selected="[]" />
          <PEmptyResults v-else>
            <template #message>
              No runs from the last 7 days
            </template>
          </PEmptyResults>
        </template>
      </p-tabs>

      <template #well>
        <WorkQueueDetails v-if="workQueue" alternate :work-queue="workQueue" />
      </template>
    </p-layout-well>
  </p-layout-default>
</template>


<script lang="ts" setup>
  import { WorkQueueDetails, PageHeadingWorkQueue, FlowRunList, WorkQueueFlowRunsList, CodeBanner, localization, useRecentFlowRunFilter } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useSubscription, useRouteParam, useSubscriptionWithDependencies } from '@prefecthq/vue-compositions'
  import { computed, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useToast } from '@/compositions'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const router = useRouter()
  const showToast = useToast()

  const tabs = computed(() => {
    const values = ['Upcoming Runs', 'Runs']

    if (!media.xl) {
      values.unshift('Details')
    }

    return values
  })

  const workQueueId = useRouteParam('id')
  const workQueueCliCommand = computed(() => `prefect agent start ${workQueue.value ? ` --work-queue "${workQueue.value.name}"` : ''}`)
  const subscriptionOptions = {
    interval: 300000,
  }

  const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId.value], subscriptionOptions)
  const workQueue = computed(() => workQueueSubscription.response)

  const workQueueName = computed(() => workQueue.value ? [workQueue.value.name] : [])
  const flowRunFilter = useRecentFlowRunFilter({ states: [], workQueues: workQueueName })

  const flowRunsFilterArgs = computed<Parameters<typeof flowRunsApi.getFlowRuns> | null>(() => workQueueName.value.length ? [flowRunFilter.value] : null)

  const flowRunsSubscription = useSubscriptionWithDependencies(flowRunsApi.getFlowRuns, flowRunsFilterArgs)
  const flowRuns = computed(() => flowRunsSubscription.response ?? [])

  const routeToQueues = (): void => {
    router.push(routes.workQueues())
  }

  const title = computed(() => {
    if (!workQueue.value) {
      return 'Work Queue'
    }
    return `Work Queue: ${workQueue.value.name}`
  })
  usePageTitle(title)

  watch(() => workQueue.value?.deprecated, value => {
    if (value) {
      showToast(localization.info.deprecatedWorkQueue, 'default', { dismissible: false, timeout: false })
    }
  })
</script>

<style>
/* This is an override since this is using nested layouts */
.work-queue__body {
  @apply
  p-0
}
</style>