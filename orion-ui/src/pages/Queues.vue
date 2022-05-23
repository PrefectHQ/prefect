<template>
  <p-layout-default class="queues">
    <template #header>
      Queues
    </template>

    <div v-for="queue in queues" :key="queue.id">
      {{ queue }}
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const filter = {}
  const subscriptionOptions = {
    interval: 30000,
  }
  const queuesSubscription = useSubscription(workQueuesApi.getWorkQueues, [filter], subscriptionOptions)
  const queues = computed(() => queuesSubscription.response ?? [])
</script>