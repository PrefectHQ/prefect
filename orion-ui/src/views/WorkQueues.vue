<template>
  <div class="work-queues">
    <PageHeader icon="robot-line" heading="Work Queues">
      <template v-if="workQueues.length" #actions>
        <WorkQueueCreateButton />
      </template>
    </PageHeader>

    <template v-if="!loading && workQueues.length">
      <WorkQueuesList :work-queues="workQueues" />
    </template>

    <template v-else-if="!loading">
      <WorkQueuesListEmptyState class="mt-3" />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import {
    WorkQueuesList,
    WorkQueuesListEmptyState,
    WorkQueueCreateButton,
    PageHeader,
    workQueuesListSubscriptionKey
  } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, provide } from 'vue'
  import { workQueuesApi } from '@/services/workQueuesApi'


  const workQueuesSubscription = useSubscription(workQueuesApi.getWorkQueues, [{}])
  provide(workQueuesListSubscriptionKey, workQueuesSubscription)

  const workQueues = computed(() => workQueuesSubscription.response ?? [])
  const loading = computed(() => workQueuesSubscription.response === undefined)
</script>
