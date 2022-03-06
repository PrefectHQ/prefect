<template>
  <div class="work-queue-list">
    <m-card shadow="sm">
      <template v-for="workQueue in workQueues" :key="workQueue.id">
        <WorkQueuesListItem :work-queue="workQueue" class="work-queue-list__item" />
      </template>
    </m-card>
  </div>
</template>

<script lang="ts" setup>
  import WorkQueuesListItem from '@/components/WorkQueuesListItem.vue'
  import { WorkQueue } from '@/models/WorkQueue'

  defineProps<{
    workQueues: WorkQueue[],
  }>()
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