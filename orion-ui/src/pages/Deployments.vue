<template>
  <p-layout-default class="deployments">
    <template #header>
      <PageHeadingDeployments />
    </template>

    <template v-if="empty">
      <DeploymentsPageEmptyState />
    </template>
    <template v-else>
      <SearchInput v-model="deploymentSearchInput" placeholder="Search deployments" label="Search by flow or deployment name" />
      <DeploymentsTable :deployments="filteredDeployments" @delete="deploymentsSubscription.refresh()" />
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { SearchInput, Deployment, DeploymentsTable, PageHeadingDeployments, DeploymentsPageEmptyState } from '@prefecthq/orion-design'
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
  const filteredDeployments = computed(()=> search(deployments.value, deploymentSearchInput.value))
  const empty = computed(() => deploymentsSubscription.executed && deployments.value.length === 0)

  const search = (array: Deployment[], text: string): Deployment[] => array.reduce<Deployment[]>((previous, current) => {
    if (current.name.toLowerCase().includes(text.toLowerCase())) {
      previous.push(current)
    }

    return previous
  }, [])
</script>