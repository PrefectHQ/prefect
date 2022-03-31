<template>
  <div class="flow-run-logs">
    <template v-for="(log, index) in logs" :key="log.id">
      <template v-if="showDivider(index)">
        <div class="flow-run-logs__divider">
          <span class="flow-run-logs__divider-time">{{ formatDateInTimeZone(log.timestamp) }}</span>
        </div>
      </template>
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
  import { isSameDay } from 'date-fns'
  import { computed, PropType } from 'vue'
  import FlowRunLog from '@/components/FlowRunLog.vue'
  import { Log } from '@/models/Log'
  import { formatDateInTimeZone } from '@/utilities/dates'

  const props = defineProps({
    logs: {
      type: Array as PropType<Log[]>,
      required: true,
    },
  })

  const empty = computed<boolean>(() => props.logs.length == 0)

  const showDivider = (index: number): boolean => {
    if (index == 0) {
      return true
    }

    const previous = props.logs[index - 1]
    const current = props.logs[index]

    return !isSameDay(previous.timestamp, current.timestamp)
  }
</script>

<style lang="scss">
.flow-run-logs {
  background-color: #fff;
  padding: var(--p-1) 0;
  display: grid;
  gap: var(--p-1);
}

.flow-run-logs__divider {
  font-family: var(--font-secondary);
  font-size: 13px;
  color: var(--grey-40);
  display: flex;
  justify-content: center;
  position: sticky;
  top: 0;
  background: #fff;

  &:after {
    content: '';
    display: block;
    position: absolute;
    height: 1px;
    left: 0;
    right: 0;
    top: 50%;
    background-color: #fff;
  }
}

.flow-run-logs__divider-time {
  background-color: #fff;
  position: relative;
  z-index: 1;
  padding: 0 var(--p-2);
}

.flow-run-logs__empty {
  text-align: center;
}
</style>