<template>
  <div class="flow-run-logs">
    <template v-for="log in logs" :key="log.id">
      <FlowRunLog :log="log" />
    </template>
  </div>
</template>

<script lang="ts">
  export default {
    name: 'FlowRunLogs',
  }
</script>

<script lang="ts" setup>
  import { PropType } from 'vue'
  import { Log } from '../models'
  import FlowRunLog from './FlowRunLog.vue'

  defineProps({
    logs: {
      type: Array as PropType<Log[]>,
      required: true,
    },
  })
</script>

<style>
.flow-run-logs {
  background-color: #fff;
  padding: var(--p-1) 0;
  display: grid;
  gap: var(--p-1);
}
</style>