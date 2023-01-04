<template>
  <p-layout-default class="worker-pools">
    <template #header>
      <PageHeadingWorkerPools />
    </template>

    <template v-if="loaded">
      <template v-if="empty">
        <WorkerPoolsPageEmptyState />
      </template>

      <template v-else>
        <WorkerPools @update="workerPoolsSubscription.refresh" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkerPools, WorkerPoolsPageEmptyState, WorkerPools } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const subscriptionOptions = {
    interval: 30000,
  }

  const workerPoolsSubscription = useSubscription(api.workerPools.getWorkerPools, [{}], subscriptionOptions)
  const workerPools = computed(() => workerPoolsSubscription.response ?? [])
  const empty = computed(() => workerPoolsSubscription.executed && workerPools.value.length == 0)
  const loaded = computed(() => workerPoolsSubscription.executed)


  usePageTitle('Worker Pools')
</script>