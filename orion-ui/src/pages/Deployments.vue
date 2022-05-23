<template>
  <p-layout-default class="deployments">
    <template #header>
      Deployments
    </template>

    <div v-for="deployment in deployments" :key="deployment.id">
      {{ deployment }}
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
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