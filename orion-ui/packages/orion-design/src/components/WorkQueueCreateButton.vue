<template>
  <m-button color="primary" miter icon="pi-add-line" @click="openCreateWorkQueuePanel">
    Create Work Queue
  </m-button>
</template>

<script lang="ts" setup>
  import Subscription from '@prefecthq/vue-compositions/src/subscribe/subscription'
  import WorkQueueEditPanel from '@/components/WorkQueueEditPanel.vue'
  import { useInjectedServices } from '@/compositions/useInjectedServices'
  import { WorkQueue } from '@/models/WorkQueue'
  import { showPanel } from '@/utilities/panels'

  const injectedServices = useInjectedServices()

  function openCreateWorkQueuePanel(): void {
    showPanel(WorkQueueEditPanel, {
      workQueue: {} as WorkQueue,
      workQueueSubscription: {} as Subscription<any>,
      ...injectedServices,
    })
  }
</script>