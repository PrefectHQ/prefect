<template>
  <p-layout-default class="work-pools">
    <template #header>
      <PageHeadingWorkPools />
    </template>

    <template v-if="loaded">
      <template v-if="empty">
        <WorkPoolsPageEmptyState />
      </template>

      <template v-else>
        <WorkPools @update="workPoolsSubscription.refresh" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useWorkspaceApi, PageHeadingWorkPools, WorkPoolsPageEmptyState, WorkPools } from '@prefecthq/prefect-ui-library'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const subscriptionOptions = {
    interval: 30000,
  }

  const workPoolsSubscription = useSubscription(api.workPools.getWorkPools, [{}], subscriptionOptions)
  const workPools = computed(() => workPoolsSubscription.response ?? [])
  const empty = computed(() => workPoolsSubscription.executed && workPools.value.length == 0)
  const loaded = computed(() => workPoolsSubscription.executed)


  usePageTitle('Work Pools')
</script>