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

      <p-tabs v-model:selected="selectedTab" :tabs="tabs">
        <template #details>
          <WorkQueueDetails v-if="workQueue" :work-queue="workQueue" />
        </template>

        <template #upcoming-runs>
          <div class="work-queue__upcoming-runs">
            <WorkQueueFlowRunsList v-if="workQueue" :work-queue="workQueue" />
            <template v-if="activeRunsBuildUp">
              <p-button secondary class="work-queue__active-runs-button" @click="showActiveRuns">
                Show active runs
              </p-button>
            </template>
          </div>
        </template>

        <template #runs>
          <FlowRunFilteredList v-model:states="states" :flow-run-filter="selectedFilter" />
        </template>
      </p-tabs>

      <template #well>
        <WorkQueueDetails v-if="workQueue" alternate :work-queue="workQueue" />
      </template>
    </p-layout-well>
  </p-layout-default>
</template>


<script lang="ts" setup>
  import { WorkQueueDetails, PageHeadingWorkQueue, FlowRunFilteredList, WorkQueueFlowRunsList, CodeBanner, localization, useRecentFlowRunFilter, inject, StateType, useFlowRunFilter, useWorkspaceApi } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed, watch, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { useToast } from '@/compositions'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'

  const router = useRouter()
  const api = useWorkspaceApi()
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

  const states = ref<StateType[]>([])
  const selectedTab = ref<string | undefined>()
  const showActiveRuns = (): void => {
    states.value = ['running', 'pending']
    selectedTab.value = 'Runs'
  }

  const subscriptionOptions = {
    interval: 300000,
  }

  const workQueueSubscription = useSubscription(api.workQueues.getWorkQueue, [workQueueId.value], subscriptionOptions)
  const workQueue = computed(() => workQueueSubscription.response)
  const workQueueConcurrency = computed(() => workQueue.value?.concurrencyLimit)
  const workQueuePaused = computed(() => workQueue.value?.isPaused)
  const activeRunsBuildUp = computed(() => !!(workQueueConcurrency.value && workQueueConcurrency.value <= activeFlowRunsCount.value && !workQueuePaused.value))

  const workQueueName = computed(() => workQueue.value ? [workQueue.value.name] : [])
  const recentFlowRunFilter = useRecentFlowRunFilter({ workQueues: workQueueName })
  const flowRunFilter = useFlowRunFilter({ workQueues: workQueueName })
  const selectedFilter = computed(() => activeRunsBuildUp.value ? flowRunFilter.value : recentFlowRunFilter.value)

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

  const activeFlowRunsFilter = useFlowRunFilter({ states: ['Running', 'Pending'], workQueues: workQueueName })
  const flowRunsCountSubscription = useSubscription(api.flowRuns.getFlowRunsCount, [activeFlowRunsFilter.value], { interval: 30000 })
  const activeFlowRunsCount = computed(()=> flowRunsCountSubscription.response ?? [])

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

.work-queue__controls-list,
.work-queue__upcoming-runs { @apply
  grid
  gap-2
}
.work-queue__active-runs-button { @apply
  justify-self-center
}
</style>