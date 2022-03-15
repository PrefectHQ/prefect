<template>
  <div class="flows-list">
    <m-card shadow="sm">
      <template v-for="flow in flows" :key="flow.id">
        <FlowsPageFlowListItem :flow="flow" />
      </template>
    </m-card>
    <template v-if="empty">
      <div class="text-center my-8">
        <h2>No results found</h2>
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import FlowsPageFlowListItem from '@/components/FlowsPageFlowListItem.vue'
  import { Flow } from '@/models/Flow'

  const props = defineProps<{
    flows: Flow[],
  }>()

  const empty = computed(() => props.flows.length === 0)
</script>