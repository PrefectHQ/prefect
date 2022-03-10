<template>
  <EmptyStateCard
    header="Create a work queue to get started"
    description="Work queues specify the criteria for flow runs to be picked up by a corresponding agent process, which runs in your execution environment. They are defined by the set of deployments, tags, or flow runners that they filter for."
  >
    <WorkQueueCreateButton />

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
  import { getDeploymentsCountKey } from '@/services/DeploymentsApi'
  import { getFlowRunsCountKey } from '@/services/FlowRunsApi'
  import { mocker } from '@/services/Mocker'

  provide(getFlowRunsCountKey, () => Promise.resolve(mocker.create('number', [0, 15])))
  provide(getDeploymentsCountKey, () => Promise.resolve(mocker.create('number', [0, 3])))

  const workQueues = [
    mocker.create('workQueue', [{ name: 'Local', isPaused: false, concurrencyLimit: 70 }]),
    mocker.create('workQueue', [{ name: 'Docker', isPaused: false, concurrencyLimit: 10 }]),
    mocker.create('workQueue', [{ name: 'Kubernetes-production', isPaused: false, concurrencyLimit: 500 }]),
  ]
</script>

<style lang="scss">
.work-queues-list-empty-state__examples {
  pointer-events: none;
  min-width: 360px;
}
</style>