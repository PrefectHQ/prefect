<template>
  <p-layout-default class="deployment">
    <template #header>
      Deployment {{ deploymentId }}

      <p-tabs :tabs="deploymentTabs">
        <template #overview>
          <div>
            Deployment Details
          </div>
          <div>
            {{ deploymentDetails }}
          </div>

          <div class="mt-2">
            params
          </div>
          <div>
            <SearchInput v-model="parameterSearchInput" />
            <div v-for="parameter, index in filteredDeploymentParameters" :key="index">
              {{ parameter[0] }} {{ parameter[1] }}
            </div>
          </div>

          <div class="mt-2">
            Deployment Flows
          </div>
          <div v-for="flow in deploymentFlows" :key="flow.id">
            {{ flow }}
          </div>
        </template>


        <template #parameters>
          <div>
            params?
          </div>
        </template>
      </p-tabs>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useRouteParam, UnionFilters, SearchInput } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowsApi } from '@/services/flowsApi'


  const deploymentTabs = ['Overview', ' Parameters']
  const deploymentId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }
  const deploymentSubscription = useSubscription(deploymentsApi.getDeployment, [deploymentId.value], subscriptionOptions)
  const deploymentDetails = computed(() => deploymentSubscription.response)

  const deploymentParameters = computed(()=> {
    if (deploymentDetails.value?.parameters) {
      const tuple = Object.entries(deploymentDetails.value.parameters)
      console.log('tuple', tuple)
      return tuple
    } return deploymentDetails.value?.parameters
  })
  const parameterSearchInput = ref('')
  const filteredDeploymentParameters = computed(()=> deploymentParameters.value ? fuzzyFilterFunction(deploymentParameters.value, parameterSearchInput.value) : [])

  type Parameter = Record<string, any>

  const fuzzyFilterFunction = (array: Parameter[], text: string): Parameter[] => array.reduce<Parameter[]>(
    (previous, current) => {
      const [key, value] = current
      const valuetype = typeof value
      const valueToString = valuetype !== 'object' ? String(value) : JSON.stringify(value)
      const checkValue = valuetype == 'string' ? value : valueToString
      if (key.toLowerCase().includes(text.toLowerCase())) {
        previous.push(current)
      } else if (valuetype.includes(text.toLowerCase())) {
        previous.push(current)
      } else if (checkValue.toLowerCase().includes(text.toLowerCase())) {
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

