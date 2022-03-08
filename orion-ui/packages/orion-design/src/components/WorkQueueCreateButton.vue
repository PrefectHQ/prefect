<template>
  <m-button color="primary" miter icon="pi-add-line" @click="openCreateWorkQueuePanel">
    Create Work Queue
  </m-button>
</template>

<script lang="ts" setup>
  import Subscription from '@prefecthq/vue-compositions/src/subscribe/subscription'
  import WorkQueuePanel from '@/components/WorkQueuePanel.vue'
  import { useInjectedServices } from '@/compositions/useInjectedServices'
  import { showPanel } from '@/utilities/panels'

  const injectedServices = useInjectedServices()

  function openCreateWorkQueuePanel(): void {
    showPanel(WorkQueuePanel, {
      workQueueId: '',
      workQueueSubscription: {} as Subscription<any>,
      openWorkQueueEditPanel: () => null,
      ...injectedServices,
    })
  }
</script>