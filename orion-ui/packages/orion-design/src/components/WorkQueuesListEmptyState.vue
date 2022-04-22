<template>
  <EmptyStateCard
    header="Create a work queue to get started"
    description="Work queues specify the criteria for flow runs to be picked up by a corresponding agent process, which runs in your execution environment. They are defined by the set of deployments, tags, or flow runners that they filter for."
  >
    <template v-if="can.create.work_queue">
      <WorkQueueCreateButton />
    </template>
    <template v-else>
      <span />
    </template>

    <template #example>
      <div class="work-queues-list-empty-state__examples">
        <template v-for="workQueue in workQueues" :key="workQueue.id">
          <WorkQueuesListItem :work-queue="workQueue" class="work-queues-list-empty-state__example" />
        </template>
      </div>
    </template>
  </EmptyStateCard>
</template>

<script lang="ts" setup>
  import { provide } from 'vue'
  import EmptyStateCard from '@/components/EmptyStateCard.vue'
  import WorkQueueCreateButton from '@/components/WorkQueueCreateButton.vue'
  import WorkQueuesListItem from '@/components/WorkQueuesListItem.vue'
  import { DeploymentsApi, deploymentsApiKey } from '@/services/DeploymentsApi'
  import { FlowRunsApi, flowRunsApiKey } from '@/services/FlowRunsApi'
  import { mocker } from '@/services/Mocker'
  import { canKey } from '@/types/permissions'
  import { inject } from '@/utilities/inject'

  // these mock the count endpoints for the WorkQueuesListItem
  // "as unknown as" is used so we don't have to mock the whole service
  provide(flowRunsApiKey, {
    getFlowRunsCount: () => Promise.resolve(mocker.create('number', [0, 15])),
  } as unknown as FlowRunsApi)

  provide(deploymentsApiKey, {
    getDeploymentsCount: () => Promise.resolve(mocker.create('number', [0, 3])),
  } as unknown as DeploymentsApi)

  const workQueues = [
    mocker.create('workQueue', [{ name: 'Local', isPaused: false, filter: { tags: ['Temporary'] }, concurrencyLimit: 70 }]),
    mocker.create('workQueue', [{ name: 'Docker', isPaused: false, filter: { tags: ['Apollo', 'DevOps'] }, concurrencyLimit: 10 }]),
    mocker.create('workQueue', [{ name: 'Kubernetes-production', isPaused: false, filter: { tags: ['Apollo', 'DevOps', 'Production'] }, concurrencyLimit: 500 }]),
  ]

  const can = inject(canKey)
</script>

<style lang="scss">
.work-queues-list-empty-state__examples {
  pointer-events: none;
  min-width: 360px;
}
</style>