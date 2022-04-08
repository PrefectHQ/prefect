<template>
  <ListItem class="work-queues-list-item">
    <div class="work-queues-list-item__title">
      <BreadCrumbs :crumbs="crumbs" tag="h2" />
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
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import BreadCrumbs from '@/components/BreadCrumbs.vue'
  import DetailsKeyValue from '@/components/DetailsKeyValue.vue'
  import ListItem from '@/components/ListItem.vue'
  import WorkQueueEditPanel from '@/components/WorkQueueEditPanel.vue'
  import WorkQueuePanel from '@/components/WorkQueuePanel.vue'
  import WorkQueuePausedTag from '@/components/WorkQueuePausedTag.vue'
  import { Crumb } from '@/models/Crumb'
  import { WorkQueue } from '@/models/WorkQueue'
  import { deploymentsApiKey } from '@/services/DeploymentsApi'
  import { workQueuesApiKey } from '@/services/WorkQueuesApi'
  import { inject } from '@/utilities/inject'
  import { showPanel } from '@/utilities/panels'
  import { workQueuesListSubscriptionKey } from '@/utilities/subscriptions'

  const props = defineProps<{ workQueue: WorkQueue }>()

  const crumbs = computed<Crumb[]>(() => [{ text: props.workQueue.name, action: openWorkQueuePanel }])


  const workQueuesListSubscription = inject(workQueuesListSubscriptionKey)
  const deploymentsApi = inject(deploymentsApiKey)
  const workQueuesApi = inject(workQueuesApiKey)

  function openWorkQueueEditPanel(workQueue: WorkQueue): void {
    const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueue.id])

    showPanel(WorkQueueEditPanel, {
      workQueue,
      workQueueSubscription,
      workQueuesListSubscription,
      deploymentsApi,
      workQueuesApi,
    })
  }

  function openWorkQueuePanel(): void {
    const workQueueId = props.workQueue.id
    const workQueueSubscription = useSubscription(workQueuesApi.getWorkQueue, [workQueueId])

    showPanel(WorkQueuePanel, {
      workQueueId,
      workQueueSubscription,
      workQueuesListSubscription,
      openWorkQueueEditPanel,
      workQueuesApi,
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
}

.work-queues-list-item__title {
  grid-area: title;
  text-align: left;
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
  flex-wrap: wrap;
}
</style>