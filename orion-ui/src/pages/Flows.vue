<template>
  <p-layout-default class="flows">
    <template #header> Flows </template>
    <SearchInput v-model="flowSearchInput" />
    <div v-for="flow in filteredFlowList" :key="flow.id">
      {{ flow }}
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
import { FlowSearch, Flow, SearchInput } from "@prefecthq/orion-design";
import { useSubscription } from "@prefecthq/vue-compositions";
import { computed, ref } from "vue";
import { flowsApi } from "@/services/flowsApi";

const filter = {}
const subscriptionOptions = {interval: 30000}
const flowsSubscription = useSubscription(flowsApi.getFlows,[filter],subscriptionOptions)
const flows = computed<Flow[]>(()=> flowsSubscription.response ?? [])
const flowSearchInput = ref('')
const filteredFlowList = computed(()=> flowFilterFunction(flows.value, flowSearchInput.value))

const flowFilterFunction=(array, text) => array?.reduce<Flow[]>(
    (previous: Flow, current: Flow): Flow[] => {
    if (current.name.toLowerCase().includes(text.toLowerCase())) {
      previous.push(current)
    }
    return previous
  },
  []
)
</script>
