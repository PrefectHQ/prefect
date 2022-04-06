<template>
  <div class="flows-list">
    <template v-if="loading">
      <m-loader
        loading
        class="text-center my-3 mx-auto"
      />
    </template>
    <template v-else>
      <m-card shadow="sm">
        <VirtualScroller :items="flows" :item-estimate-height="70" @bottom="emit('bottom')">
          <template #default="{ item }">
            <FlowsPageFlowListItem :flow="item">
              <template #flow-filters="{ flow }">
                <slot name="flow-filters" :flow="flow" />
              </template>
            </FlowsPageFlowListItem>
          </template>
        </VirtualScroller>
      </m-card>
    </template>
    <template v-if="empty">
      <div class="text-center my-8">
        <h2>No results found</h2>
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import VirtualScroller from './VirtualScroller.vue'
  import FlowsPageFlowListItem from '@/components/FlowsPageFlowListItem.vue'
  import { Flow } from '@/models/Flow'

  const props = defineProps<{
    flows: Flow[],
    loading: boolean,
  }>()

  const emit = defineEmits<{
    (event: 'bottom'): void,
  }>()

  const empty = computed(() => props.flows.length === 0)
</script>