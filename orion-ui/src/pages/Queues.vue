<template>
  <p-layout-default class="queues">
    <template #header>
      <PageHeadingQueues />
    </template>

    <template v-if="loaded">
      <template v-if="empty">
        <WorkQueuesPageEmptyState />
      </template>
      <template v-else>
        <SearchInput v-model="searchInput" />
        <QueuesTable :queues="filteredQueues" @delete="queuesSubscription.refresh()" @clear="clear" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { SearchInput, WorkQueue, QueuesTable, PageHeadingQueues, WorkQueuesPageEmptyState } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { workQueuesApi } from '@/services/workQueuesApi'

  const filter = {}
  const subscriptionOptions = {
    interval: 30000,
  }
  const queuesSubscription = useSubscription(workQueuesApi.getWorkQueues, [filter], subscriptionOptions)
  const queues = computed(() => queuesSubscription.response ?? [])
  const empty = computed(() => queuesSubscription.executed && queues.value.length == 0)
  const loaded = computed(() => queuesSubscription.executed)
  const searchInput = ref('')
  const filteredQueues = computed(() => search(queues.value, searchInput.value))

  const search = (array: WorkQueue[], text: string): WorkQueue[] => array.reduce<WorkQueue[]>((previous, current) => {
    if (current.name.toLowerCase().includes(text.toLowerCase())) {
      previous.push(current)
    }

    return previous
  }, [])

  const clear = (): void => {
    searchInput.value = ''
  }
</script>