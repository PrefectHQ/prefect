<template>
  <div class="flows-list">
    <m-card shadow="sm">
      <template v-for="flow in flows" :key="flow.id">
        <FlowsPageFlowListItem :flow="flow" class="flows-list__item" />
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

<style lang="scss">
.flows-list__item {
  &:not(:first-of-type) {
    border-top: 1px solid var(--secondary-hover);
  }
}
</style>