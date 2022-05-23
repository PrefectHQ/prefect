<template>
  <p-layout-default class="flows">
    <template #header>
      Flows
    </template>
    <div v-for="flow in flows" :key="flow.id">
      {{ flow }}
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { flowsApi } from '@/services/flowsApi'

  const filter = {}
  const subscriptionOptions = {
    interval: 30000,
  }
  const flowsSubscription = useSubscription(flowsApi.getFlows, [filter], subscriptionOptions)
  const flows = computed(() => flowsSubscription.response ?? [])
</script>