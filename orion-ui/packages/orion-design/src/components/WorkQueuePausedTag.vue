<template>
  <m-tag class="work-queues-list-item__paused" :color="workQueue.isPaused ? 'grey-40' : 'primary'">
    <span>{{ workQueue.isPaused ? 'paused' : 'active' }}</span>
  </m-tag>
</template>

<script lang="ts" setup>
  import { WorkQueue } from '@/models/WorkQueue'

  defineProps<{
    workQueue: WorkQueue,
  }>()
</script>
