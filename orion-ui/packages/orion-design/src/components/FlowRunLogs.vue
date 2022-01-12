<template>
  <div class="flow-run-logs">
    <template v-for="log in logs" :key="log.id">
      <FlowRunLog :log="log" />
    </template>
    <template v-if="empty">
      <slot name="empty">
        <div class="flow-run-logs__empty">
          <p>No logs to show</p>
        </div>
      </slot>
    </template>
  </div>
</template>

<script lang="ts">
  export default {
    name: 'FlowRunLogs',
  }
</script>

<script lang="ts" setup>
  import { computed, PropType } from 'vue'
  import { Log } from '../models'
  import FlowRunLog from './FlowRunLog.vue'

  const props = defineProps({
    logs: {
      type: Array as PropType<Log[]>,
      required: true,
    },
  })

  const empty = computed<boolean>(() => props.logs.length == 0)
</script>

<style>
.flow-run-logs {
  background-color: #fff;
  padding: var(--p-1) 0;
  display: grid;
  gap: var(--p-1);
}

.flow-run-logs__empty {
  text-align: center;
}
</style>