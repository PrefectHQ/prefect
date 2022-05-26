<template>
  <p-layout-default class="flows">
    <template #header>
      Flows
    </template>
    <FlowSearch v-model="flows" />
    <div v-for="flow in flows" :key="flow.id">
      {{ flow }}
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { FlowSearch, Flow } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { flowsApi } from '@/services/flowsApi'

  const filter = {}
  const subscriptionOptions = {
    interval: 30000,
  }
  const flowsSubscription = useSubscription(flowsApi.getFlows, [filter], subscriptionOptions)
  const filteredFlowList=ref(null)
  const flows = computed<Flow[]>({
    get() {
      return filteredFlowList.value ?? flowsSubscription.response ?? []
    },
    set(value: Flow[] | null) {
      filteredFlowList.value = value
    },
  })
</script>