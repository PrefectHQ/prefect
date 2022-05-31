<template>
  <p-layout-default class="deployments">
    <template #header>
      Deployments
    </template>

    <SearchInput v-model="deploymentSearchInput" placeholder="Search..." label="Search by flow or deployment name" />
    <DeploymentsTable :deployments="filteredDeployments" @delete="deploymentsSubscription.refresh()" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { SearchInput, Deployment, DeploymentsTable } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'

  const filter = {}
  const subscriptionOptions = {
    interval: 30000,
  }
  const deploymentsSubscription = useSubscription(deploymentsApi.getDeployments, [filter], subscriptionOptions)
  const deployments = computed(() => deploymentsSubscription.response ?? [])
  const deploymentSearchInput = ref('')
  const filteredDeployments = computed(()=> fuzzyFilterFunction(deployments.value, deploymentSearchInput.value))

  const fuzzyFilterFunction = (array: Deployment[], text: string): Deployment[] => array.reduce<Deployment[]>(
    (previous, current) => {
      if (current.name.toLowerCase().includes(text.toLowerCase())) {
        previous.push(current)
      }
      return previous
    }, [])
</script>