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

    <p-key-value>
      <template #label>
        <div class="queue-label">
          Description
        </div>
      </template>

      <template #value>
        {{ workQueueDetails?.description }}
      </template>
    </p-key-value>

    <p-key-value>
      <template #label>
        <div class="queue-label">
          Work Queue ID
        </div>
      </template>

      <template #value>
        {{ workQueueDetails?.id }}
      </template>
    </p-key-value>

    <p-key-value>
      <template #label>
        <div class="queue-label">
          Flow Run Concurrency
        </div>
      </template>

      <template #value>
        {{ workQueueDetails?.concurrencyLimit }}
      </template>
    </p-key-value>

    <p-key-value>
      <template #label>
        <div class="queue-label">
          Created
        </div>
      </template>

      <template #value>
        {{ workQueueDetails?.created }}
      </template>
    </p-key-value>


    <div class="queue-filter-label">
      Filters
    </div>

    <p-key-value>
      <template #label>
        <div class="queue-label">
          Tags
        </div>
      </template>

      <template #value>
        <p-tag v-for="tag in workQueueDetails?.filter.tags" :key="tag">
          {{ tag }}
        </p-tag>
      </template>
    </p-key-value>

    <p-key-value>
      <template #label>
        <div class="queue-label">
          Deployments
        </div>
      </template>

      <template #value>
        <DeploymentsTable :deployments="workQueueDeployments" />
      </template>
    </p-key-value>

    <p-key-value>
      <template #label>
        <div class="queue-label">
          Flow Runners
        </div>
      </template>

      <template #value>
        <p-checkbox v-for="runners in workQueueDetails?.filter.flowRunnerTypes" :key="runners" v-model="flowRunners" :label="runners" />
      </template>
    </p-key-value>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useRouteParam,  UnionFilters, DeploymentsTable } from '@prefecthq/orion-design'
  import { PKeyValue } from '@prefecthq/prefect-design'
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
  mt-4
}

.queue-filter-label{ @apply
  text-gray-500
  mt-6
}
</style>