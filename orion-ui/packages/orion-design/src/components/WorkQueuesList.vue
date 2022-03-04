<template>
  <div class="work-queue-list">
    <m-card shadow="sm">
      <template v-for="workQueue in workQueues" :key="workQueue.id">
        <WorkQueueItem :work-queue="workQueue" class="work-queue-list__item" />
      </template>
    </m-card>
  </div>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, inject } from 'vue'
  import WorkQueueItem from '@/components/WorkQueuesListItem.vue'
  import { PaginatedFilter } from '@/services/Filter'
  import { workQueuesApi, getWorkQueuesKey } from '@/services/WorkQueuesApi'

  const props = defineProps<{
    filter: PaginatedFilter,
  }>()

  const getWorkQueues = inject(getWorkQueuesKey, workQueuesApi.getWorkQueues)
  const workQueuesSubscription = useSubscription(getWorkQueues, [props.filter])
  const workQueues = computed(() => workQueuesSubscription.response.value ?? [])
</script>

<style lang="scss">
.work-queue-list {
    padding: 10px;
}

.work-queue-list__item {
  &:not(:first-of-type) {
    border-top: 1px solid var(--secondary-hover);
  }
}

.work-queue-list__empty-state {
  text-align: center;
  margin: var(--m-8) 0;
}
</style>