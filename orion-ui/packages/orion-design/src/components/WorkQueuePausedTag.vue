<template>
  <SmallTag class="work-queues-list-item__paused" :miter="false" :color="workQueue?.isPaused ? 'grey-40' : 'success'">
    <span>{{ text }}</span>
  </SmallTag>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import SmallTag from '@/components/SmallTag.vue'
  import { WorkQueue } from '@/models/WorkQueue'

  const props = defineProps<{
    workQueue: WorkQueue | null,
  }>()

  const text = computed(() => {
    if (!props.workQueue) {
      return '--'
    }
    return props.workQueue.isPaused ? 'paused' : 'active'
  })
</script>
