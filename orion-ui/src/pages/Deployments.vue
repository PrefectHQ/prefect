<template>
  <p-layout-default class="deployments">
    <template #header>
      Deployments
    </template>

    <DeploymentsTable :deployments="deployments" @delete="deploymentsSubscription.refresh()" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { DeploymentsTable } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'

  const filter = {}
  const subscriptionOptions = {
    interval: 30000,
  }
  const deploymentsSubscription = useSubscription(deploymentsApi.getDeployments, [filter], subscriptionOptions)
  const deployments = computed(() => deploymentsSubscription.response ?? [])
</script>