<template>
  <div class="queue">
    Queue {{ workQueueId }}
  </div>

  <div>
    Queue Details
  </div>
  <div>
    {{ workQueueDetails }}
  </div>
</template>

<script lang="ts" setup>
  import { useRouteParam } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const workQueueId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }
  const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId.value], subscriptionOptions)
  const workQueueDetails = computed(() => workQueueSubscription.response ?? [])
</script>

<style>
.queue {}
</style>