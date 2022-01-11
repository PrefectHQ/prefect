<template>
  <FlowRunLogs class="flow-run-logs-tab-content" :logs="logs" />
</template>

<script lang="ts" setup>
import {
  Logs,
  LogsRequestFilter,
  FlowRunLogs,
  Log
} from '@prefecthq/orion-design'
import { computed, defineProps, ref } from 'vue'

const props = defineProps({
  flowRunId: {
    type: String,
    required: true
  }
})

const logs = ref<Log[]>([])

// todo: paginate this with limit/offset
const filter = computed<LogsRequestFilter>(() => ({
  logs: {
    flow_run_id: {
      any_: [props.flowRunId]
    }
  }
}))

logs.value = await Logs.filter(filter.value)
</script>
