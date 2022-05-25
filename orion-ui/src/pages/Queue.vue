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
      <span class="text-gray-900 font-normal">Description:</span>
      <div>{{ workQueueDetails?.description }}</div>
    </div>

    <div>
      <span class="text-gray-900 font-normal">Work Queue ID:</span>
      <div>{{ workQueueDetails?.id }}</div>
    </div>

    <div>
      <span class="text-gray-900 font-normal">Flow Run Concurrency</span>
      <div>{{ workQueueDetails?.concurrencyLimit }}</div>
    </div>

    <div>
      <span class="text-gray-900 font-normal">Created</span>
      <div>{{ workQueueDetails?.created }}</div>
    </div>

    <div class="text-gray-500">
      Filters
    </div>

    <div>
      <span class="text-gray-900 font-normal">Tags</span>
      <p-tag-wrapper :tags="workQueueDetails?.filter.tags" />
    </div>

    <div>
      <span class="text-gray-900 font-normal">Deployments</span>
      <div>{{ workQueueDetails?.filter.deploymentIds }}</div>
    </div>

    <div>
      <span class="text-gray-900 font-normal">Flow Runners</span>
      <p-checkbox v-for="runners in workQueueDetails?.filter.flowRunnerTypes" :key="runners" v-model="flowRunners" :label="runners" />
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useRouteParam } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { workQueuesApi } from '@/services/workQueuesApi'
  const flowRunners = ref([])
  const workQueueId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }
  const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId.value], subscriptionOptions)
  const workQueueDetails = computed(() => workQueueSubscription.response)
</script>