<template>
  <ListItem class="work-queues-list-item">
    <div class="work-queues-list-item__title">
      <BreadCrumbs :crumbs="crumbs" @click="openWorkQueuePanel(workQueue.id)" />
    </div>

    <div class="work-queues-list-item__status">
      <WorkQueuePausedTag :work-queue="workQueue" />

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
  import { computed } from 'vue'
  import BreadCrumbs from '@/components/BreadCrumbs.vue'
  import DetailsKeyValue from '@/components/DetailsKeyValue.vue'
  import ListItem from '@/components/ListItem.vue'
  import WorkQueueEditPanel from '@/components/WorkQueueEditPanel.vue'
  import WorkQueuePanel from '@/components/WorkQueuePanel.vue'
  import WorkQueuePausedTag from '@/components/WorkQueuePausedTag.vue'
  import { useInjectedServices } from '@/compositions/useInjectedServices'
  import { WorkQueue } from '@/models/WorkQueue'

  const props = defineProps<{ workQueue: WorkQueue }>()

  const injectedServices = useInjectedServices()
  const crumbs = computed(() => [{ text: props.workQueue.name, to: `#${props.workQueue.id}` }])

  function openWorkQueueEditPanel(workQueue: WorkQueue): void {
    injectedServices.useShowPanel(WorkQueueEditPanel, {
      workQueue,
      ...injectedServices,
    })
  }

  function openWorkQueuePanel(workQueueId: string): void {
    injectedServices.useShowPanel(WorkQueuePanel, {
      workQueueId,
      openWorkQueueEditPanel,
      ...injectedServices,
    })
  }
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