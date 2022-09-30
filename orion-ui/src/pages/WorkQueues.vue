<template>
  <p-layout-default class="queues">
    <template #header>
      <PageHeadingWorkQueues />
    </template>

    <template v-if="loaded">
      <template v-if="empty">
        <WorkQueuesPageEmptyState />
      </template>

      <template v-else>
        <WorkQueuesTable :work-queues="workQueues" @update="workQueuesSubscription.refresh()" @delete="workQueuesSubscription.refresh()" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { WorkQueuesTable, PageHeadingWorkQueues, WorkQueuesPageEmptyState } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const subscriptionOptions = {
    interval: 30000,
  }

  const workQueuesSubscription = useSubscription(workQueuesApi.getWorkQueues, [{}], subscriptionOptions)
  const workQueues = computed(() => workQueuesSubscription.response ?? [])
  const empty = computed(() => workQueuesSubscription.executed && workQueues.value.length == 0)
  const loaded = computed(() => workQueuesSubscription.executed)

  usePageTitle('Work Queues')
</script>