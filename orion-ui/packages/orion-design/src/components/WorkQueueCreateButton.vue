<template>
  <m-button color="primary" miter icon="pi-add-line" @click="openCreateWorkQueuePanel">
    Create Work Queue
  </m-button>
</template>

<script lang="ts" setup>
  // import WorkQueueCreatePanel from '@/components/WorkQueueCreatePanel.vue'
  import { useInjectedServices } from '@/compositions/useInjectedServices'
  import { showPanel } from '@/utilities/panels'

  const injectedServices = useInjectedServices()

  function openCreateWorkQueuePanel(): void {
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-expect-error
    showPanel('div', {
      ...injectedServices,
    })
  }
</script>