<template>
  <m-button color="primary" miter icon="pi-add-line" @click="openCreateWorkQueuePanel">
    Create Work Queue
  </m-button>
</template>

<script lang="ts" setup>
  import WorkQueueCreatePanel from '@/components/WorkQueueCreatePanel.vue'
  import { deploymentsApiKey } from '@/services/DeploymentsApi'
  import { workQueuesApiKey } from '@/services/WorkQueuesApi'
  import { inject } from '@/utilities/inject'
  import { showPanel } from '@/utilities/panels'
  import { workQueuesListSubscriptionKey } from '@/utilities/subscriptions'

  const workQueuesListSubscription = inject(workQueuesListSubscriptionKey)
  const deploymentsApi = inject(deploymentsApiKey)
  const workQueuesApi = inject(workQueuesApiKey)

  function openCreateWorkQueuePanel(): void {
    showPanel(WorkQueueCreatePanel, {
      workQueuesListSubscription,
      deploymentsApi,
      workQueuesApi,
    })
  }
</script>