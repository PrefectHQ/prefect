<template>
  <p-layout-default class="deployment">
    <template #header>
      Deployment {{ deploymentId }}
    </template>

    <p-tabs :tabs="deploymentTabs">
      <template #overview>
        <div>
          Deployment Details
        </div>
        <div>
          {{ deploymentDetails }}
        </div>

        <div class="mt-2">
          Deployment Flows
        </div>
        <div v-for="flow in deploymentFlows" :key="flow.id">
          {{ flow }}
        </div>
      </template>


      <template #parameters>
        <SearchInput v-model="parameterSearchInput" placeholder="Search parameters" label="Search parameters by key, value, type" />
        <div v-for="parameter, index in filteredDeploymentParameters" :key="index">
          {{ parameter[0] }} {{ parameter[1] }}
        </div>
      </template>
    </p-tabs>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useRouteParam, UnionFilters, SearchInput } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowsApi } from '@/services/flowsApi'


  const deploymentTabs = ['Overview', 'Parameters']
  const deploymentId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }
  const deploymentSubscription = useSubscription(deploymentsApi.getDeployment, [deploymentId.value], subscriptionOptions)
  const deploymentDetails = computed(() => deploymentSubscription.response)

  const deploymentParameters = computed(() => Object.entries(deploymentDetails.value?.parameters))
  const parameterSearchInput = ref('')
  const filteredDeploymentParameters = computed(()=> deploymentParameters.value ? fuzzyFilterFunction(deploymentParameters.value, parameterSearchInput.value) : [])

  type Parameter = Record<string, any>

  const fuzzyFilterFunction = (array: Parameter[], text: string): Parameter[] => array.reduce<Parameter[]>(
    (previous, current) => {
      const [key, value] = current
      const searchString = `${JSON.stringify(value)} ${key} ${typeof value}`.toLowerCase()
      if (searchString.includes(text.toLowerCase())) {
        previous.push(current)
      }
      return previous
    }, [])

  const deploymentFlowFilter = computed<UnionFilters>(() => ({
    deployments: {
      id: {
        any_: [deploymentId.value],
      },
    },
  }))
  const deploymentFlowsSubscription = useSubscription(flowsApi.getFlows, [deploymentFlowFilter], subscriptionOptions)
  const deploymentFlows = computed(() => deploymentFlowsSubscription.response ?? [])
</script>

