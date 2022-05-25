<template>
  <p-layout-default class="queue">
    <template #header>
      Queue {{ workQueueId }}
    </template>

    <div>
      Queue Details
    </div>
    <div>
      {{ workQueueDetails }}
    </div>

    <div>
      <span class="queue-label">Description:</span>
      <div>{{ workQueueDetails?.description }}</div>
    </div>

    <div class="mt-4">
      <span class="queue-label">Work Queue ID:</span>
      <div>{{ workQueueDetails?.id }}</div>
    </div>

    <div class="mt-4">
      <span class="queue-label">Flow Run Concurrency</span>
      <div>{{ workQueueDetails?.concurrencyLimit }}</div>
    </div>

    <div class="mt-4">
      <span class="queue-label">Created</span>
      <div>{{ workQueueDetails?.created }}</div>
    </div>

    <div class="queue-filter-label">
      Filters
    </div>

    <div>
      <span class="queue-label">Tags</span>
      <p-tag-wrapper :tags="workQueueDetails?.filter.tags" />
    </div>

    <div>
      <span class="queue-label">Deployments</span>
      <div v-for="deployment in workQueueDeployments" :key="deployment.id">
        {{ deployment?.name }}
      </div>
    </div>

    <div>
      <span class="queue-label">Flow Runners</span>
      <p-checkbox v-for="runners in workQueueDetails?.filter.flowRunnerTypes" :key="runners" v-model="flowRunners" :label="runners" />
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useRouteParam,  UnionFilters } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { workQueuesApi } from '@/services/workQueuesApi'
  const flowRunners = ref([])
  const workQueueId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }
  const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId.value], subscriptionOptions)
  const workQueueDetails = computed(() => workQueueSubscription.response)
  const workQueueDeploymentIds = computed(() => workQueueDetails?.value?.filter?.deploymentIds)

  const workQueueDeploymentFilter = computed<UnionFilters>(() => ({
    deployments: {
      id: {
        any_: workQueueDeploymentIds.value,
      },
    },
  }))
  const workQueueDeploymentSubscription = useSubscription(deploymentsApi.getDeployments, [workQueueDeploymentFilter], subscriptionOptions)
  const workQueueDeployments = computed(() => workQueueDeploymentSubscription.response)
</script>

<style>
.queue-label { @apply
  text-gray-900
  font-bold
}

.queue-filter-label{ @apply
  text-gray-500
  mt-6
}
</style>