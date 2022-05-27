<template>
  <p-layout-default class="flow">
    <template #header>
      Flow {{ flowId }}

      <p-tabs :tabs="flowTabs">
        <template #deployments>
          <SearchInput v-model="flowDeploymentSearchInput" placeholder="Search..." label="Search by deployment name" />
          <div v-for="deployment in filteredFlowDeployments" :key="deployment.id" class="mb-4">
            {{ deployment }}
          </div>
        </template>
      </p-tabs>
    </template>

    <div>
      Flow Details
    </div>
    <div>
      {{ flowDetails }}
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useRouteParam, UnionFilters, SearchInput, Deployment } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowsApi } from '@/services/flowsApi'

  const flowTabs = ['Deployments']

  const flowId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }
  const flowSubscription = useSubscription(flowsApi.getFlow, [flowId.value], subscriptionOptions)
  const flowDetails = computed(() => flowSubscription.response ?? [])

  const flowDeploymentFilter = computed<UnionFilters>(() => ({
    flows: {
      id: {
        any_: [flowId.value],
      },
    },
  }))
  const flowDeploymentsSubscription = useSubscription(deploymentsApi.getDeployments, [flowDeploymentFilter], subscriptionOptions)
  const flowDeployments = computed(() => flowDeploymentsSubscription.response ?? [])

  const flowDeploymentSearchInput = ref('')
  const filteredFlowDeployments = computed(()=> fuzzyFilterFunction(flowDeployments.value, flowDeploymentSearchInput.value))

  const fuzzyFilterFunction = (array: Deployment[], text: string): Deployment[] => array.reduce<Deployment[]>(
    (previous, current) => {
      if (current.name.toLowerCase().includes(text.toLowerCase())) {
        previous.push(current)
      }
      return previous
    }, [])
</script>