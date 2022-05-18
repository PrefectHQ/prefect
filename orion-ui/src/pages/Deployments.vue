<template>
  <div class="deployments">
    Deployments
  </div>

  <div v-for="deployment in deployments" :key="deployment.id">
    {{ deployment }}
  </div>
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


<style>
.deployments {}
</style>