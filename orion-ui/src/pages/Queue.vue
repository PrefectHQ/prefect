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

    <p-key-value label="Description" :value="workQueueDescription" />

    <p-key-value label="Work Queue ID" :value="workQueueID" />

    <p-key-value label="Flow Run Concurrency" :value="workQueueFlowRunConcurrency" />

    <p-key-value label="Created" :value="workQueueCreated" />

    <div>
      Filters
    </div>

    <p-key-value label="Tags">
      <template #value>
        <p-tag v-for="tag in workQueueDetails?.filter.tags" :key="tag">
          {{ tag }}
        </p-tag>
      </template>
    </p-key-value>

    <p-key-value label="Deployments">
      <template #value>
        <DeploymentsTable :deployments="workQueueDeployments" />
      </template>
    </p-key-value>

    <p-key-value label="Flow Runners">
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

  const workQueueDescription = computed(() => workQueueDetails.value?.description ?? '')
  const workQueueID = computed(() => workQueueDetails.value?.id ?? '')
  const workQueueFlowRunConcurrency = computed(() => workQueueDetails.value?.concurrencyLimit ?? 0)
  const workQueueCreated = computed(() => String(workQueueDetails.value?.created) ?? '')

  const workQueueDeploymentFilter = computed<UnionFilters>(() => ({
    deployments: {
      id: {
        any_: workQueueDeploymentIds.value,
      },
    },
  }))
  const workQueueDeploymentSubscription = useSubscription(deploymentsApi.getDeployments, [workQueueDeploymentFilter], subscriptionOptions)
  const workQueueDeployments = computed(() => workQueueDeploymentSubscription.response ?? [])
</script>

