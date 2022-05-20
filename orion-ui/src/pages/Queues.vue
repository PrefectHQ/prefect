<template>
  <div class="queues">
    Queues
  </div>

  <div v-for="queue in queues" :key="queue.id">
    {{ queue }}
  </div>
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

<style>
.queues {}
</style>