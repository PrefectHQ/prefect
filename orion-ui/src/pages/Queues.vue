<template>
  <p-layout-default class="queues">
    <template #header>
      Queues
    </template>

    <SearchInput v-model="workQueueSearchInput" />
    <div v-for="queue in filteredQueues" :key="queue.id" class="mb-4">
      {{ queue }}
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { SearchInput, WorkQueue } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const filter = {}
  const subscriptionOptions = {
    interval: 30000,
  }
  const queuesSubscription = useSubscription(workQueuesApi.getWorkQueues, [filter], subscriptionOptions)
  const queues = computed(() => queuesSubscription.response ?? [])
  const workQueueSearchInput = ref('')
  const filteredQueues = computed(()=> fuzzyFilterFunction(queues.value, workQueueSearchInput.value))

  const fuzzyFilterFunction = (array: WorkQueue[], text: string): WorkQueue[] => array.reduce<WorkQueue[]>(
    (previous, current) => {
      if (current.name.toLowerCase().includes(text.toLowerCase())) {
        previous.push(current)
      }
      return previous
    }, [])
</script>