<template>
  <p-layout-default class="queue">
    <template #header>
      <PageHeadingWorkQueue v-if="workQueue" :queue="workQueue" @update="workQueueSubscription.refresh" @delete="routeToQueues" />
    </template>

    <p-key-value label="Description" :value="workQueueDescription" />

    <p-key-value label="Work Queue ID" :value="workQueueID" />

    <p-key-value label="Flow Run Concurrency" :value="workQueueFlowRunConcurrency" />

    <p-key-value label="Created" :value="workQueueCreated" />

    <p-key-value label="Tags">
      <template v-if="workQueueTags.length" #value>
        <p-tags :tags="workQueueTags" class="mt-2" />
      </template>
    </p-key-value>

    <p-key-value label="Deployments">
      <template #value>
        <span v-if="emptyWorkQueueDeployments">All Deployments</span>
        <span v-for="(deployment, index) in workQueueDeployments" v-else :key="deployment.id">
          <span v-if="index !== 0">, </span>
          <p-link :to="routes.deployment(deployment.id)">
            {{ deployment.name }}
          </p-link>
        </span>
      </template>
    </p-key-value>

    <p-key-value label="Flow Runners">
      <template #value>
        <FlowRunnerCheckboxes v-model:selected="workQueueFlowRunners" disabled />
      </template>
    </p-key-value>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useRouteParam, UnionFilters, FlowRunnerCheckboxes, PageHeadingWorkQueue } from '@prefecthq/orion-design'
  import { PKeyValue, formatDate } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const router = useRouter()

  const workQueueId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }

  const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId.value], subscriptionOptions)
  const workQueue = computed(() => workQueueSubscription.response)
  const workQueueDeploymentIds = computed(() => workQueue?.value?.filter?.deploymentIds ?? [])
  const workQueueDescription = computed(() => workQueue.value?.description ?? '')
  const workQueueID = computed(() => workQueue.value?.id ?? '')
  const workQueueFlowRunConcurrency = computed(() => workQueue.value?.concurrencyLimit ?? 'Unlimited')
  const workQueueCreated = computed(() => {
    if (workQueue.value?.created) {
      return formatDate(workQueue.value?.created)
    }
    return ''
  })
  const workQueueFlowRunners = computed(() => workQueue.value?.filter?.flowRunnerTypes ?? [])
  const workQueueTags = computed(() => workQueue.value?.filter.tags ?? [])

  const workQueueDeploymentFilter = computed<UnionFilters>(() => ({
    deployments: {
      id: {
        any_: workQueueDeploymentIds.value,
      },
    },
  }))
  const workQueueDeploymentSubscription = useSubscription(deploymentsApi.getDeployments, [workQueueDeploymentFilter], subscriptionOptions)
  const workQueueDeployments = computed(() => workQueueDeploymentSubscription.response ?? [])
  const emptyWorkQueueDeployments = computed(() => workQueueDeployments.value?.length === 0)

  const routeToQueues = (): void => {
    router.push(routes.queues())
  }
</script>
