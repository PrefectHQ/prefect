<template>
  <ListItem class="work-queues-list-item">
    <div class="work-queues-list-item__title">
      <BreadCrumbs :crumbs="crumbs" />
    </div>

    <div class="work-queues-list-item__status">
      <WorkQueuePausedTag />

      <m-tags :tags="workQueue.filter?.tags" />
    </div>

    <div class="work-queues-list-item__concurrency">
      <DetailsKeyValue
        label="Concurrency"
        :value="workQueue.concurrencyLimit ? workQueue.concurrencyLimit.toLocaleString() : 'No Limit'"
      />
    </div>
  </ListItem>
</template>

<script lang="ts" setup>
  import BreadCrumbs from '@/components/BreadCrumbs.vue'
  import DetailsKeyValue from '@/components/DetailsKeyValue.vue'
  import ListItem from '@/components/ListItem.vue'
  import { WorkQueue } from '@/models/WorkQueue'

  const props = defineProps<{ workQueue: WorkQueue }>()

  const crumbs = [{ text: props.workQueue.name, to: '#' }]
</script>

<style lang="scss">
.work-queues-list-item {
  display: grid;
  grid-template-areas:
    'title filters concurrency'
    'status filters concurrency';
  grid-template-columns: 1fr min-content min-content;
  column-gap: var(--m-1);
  row-gap: 2px;
  padding: var(--p-1) var(--p-2);
}

.work-queues-list-item__title {
  grid-area: title;
  text-align: left;
  margin-top: calc(var(--m-1) * -1);
}

.work-queues-list-item__filters {
  grid-area: filters;
  display: flex;
  align-items: center;
}

.work-queues-list-item__concurrency {
  grid-area: concurrency;
  display: flex;
  align-items: center;
}

.work-queues-list-item__status {
  grid-area: status;
  display: flex;
  gap: 2px;
}
</style>