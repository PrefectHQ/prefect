<template>
  <p-layout-default class="queue">
    <template #header>
      Queue {{ workQueueId }}
    </template>

    <div class="mb-2">
      <p-key-value label="Description" :value="workQueueDescription" />
    </div>

    <div class="mb-2">
      <p-key-value label="Work Queue ID" :value="workQueueID" />
    </div>

    <div class="mb-2">
      <p-key-value label="Flow Run Concurrency" :value="workQueueFlowRunConcurrency" />
    </div>

    <div class="mb-2">
      <p-key-value label="Created" :value="workQueueCreated" />
    </div>

    <div class="mb-2">
      <p-key-value label="Tags">
        <template #value>
          <p-tag v-for="tag in workQueueTags" :key="tag">
            {{ tag }}
          </p-tag>
        </template>
      </p-key-value>
    </div>

    <div class="mb-2">
      <p-key-value label="Deployments">
        <template #value>
          <div v-for="deployment in workQueueDeployments" :key="deployment.id">
            <router-link :to="`/deployment/${deployment.id}`">
              {{ deployment.name }}
            </router-link>
          </div>
        </template>
      </p-key-value>
    </div>

    <div class="mb-2">
      <p-key-value label="Flow Runners">
        <template #value>
          <p-checkbox
            v-for="runner in flowRunnerTypes"
            :key="runner.value"
            v-model="flowRunners"
            :label="runner.label"
            :value="runner.value"
            editor="checkbox"
            :disabled="disableCheckbox"
          />
        </template>
      </p-key-value>
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useRouteParam, UnionFilters, FlowRunnerType, formatDate } from '@prefecthq/orion-design'
  import { PKeyValue } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { workQueuesApi } from '@/services/workQueuesApi'
  const disableCheckbox = ref(true)
  const workQueueId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }

  const flowRunnerTypes: { label: string, value: FlowRunnerType }[] = [
    { label: 'Universal', value: 'universal' },
    { label: 'Kubernetes', value: 'kubernetes' },
    { label: 'Docker', value: 'docker' },
    { label: 'Subprocess', value: 'subprocess' },
  ]

  const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId.value], subscriptionOptions)
  const workQueueDetails = computed(() => workQueueSubscription.response)
  const workQueueDeploymentIds = computed(() => workQueueDetails?.value?.filter?.deploymentIds)
  const workQueueDescription = computed(() => workQueueDetails.value?.description ?? '')
  const workQueueID = computed(() => workQueueDetails.value?.id ?? '')
  const workQueueFlowRunConcurrency = computed(() => workQueueDetails.value?.concurrencyLimit ?? 'Unlimited')
  const workQueueCreated = computed(() => {
    if (workQueueDetails.value?.created) {
      return formatDate(workQueueDetails.value?.created)
    }
    return ''
  })
  const workQueueFlowRunners = computed(() => workQueueDetails.value?.filter?.flowRunnerTypes ?? [])
  const workQueueTags = computed(() => workQueueDetails.value?.filter.tags ?? [])

  const flowRunners = ref(workQueueFlowRunners.value)

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

