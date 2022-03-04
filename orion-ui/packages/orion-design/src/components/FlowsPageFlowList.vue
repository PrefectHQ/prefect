<template>
  <div class="flows-list">
    <m-card shadow="sm">
      <template v-for="flow in flows" :key="flow.id">
        <FlowsPageFlowListItem :flow="flow" />
      </template>
    </m-card>
  </div>
</template>

<script lang="ts" setup>
  import FlowsPageFlowListItem from '@/components/FlowsPageFlowListItem.vue'
  import { Flow } from '@/models/Flow'

  defineProps<{
    flows: Flow[],
  }>()
</script>