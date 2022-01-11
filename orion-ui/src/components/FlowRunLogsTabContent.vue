<template>
  <div class="flow-run-logs-tabs-content">
    <FlowRunLogs class="flow-run-logs-tab-content" :logs="logs" />
    <template v-if="loading">
      <div class="flow-run-logs-tabs-content__loading">
        <m-loader :loading="true" class="flow-run-logs-tabs-content__loader" />
        <span>Run in progress...</span>
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
import {
  Logs,
  LogsRequestFilter,
  FlowRunLogs,
  Log
} from '@prefecthq/orion-design'
import { subscribe } from '@prefecthq/vue-compositions'
import { SubscriptionOptions } from '@prefecthq/vue-compositions/src/subscribe/types'
import { computed, defineProps, ref, watch } from 'vue'

const props = defineProps({
  flowRunId: {
    type: String,
    required: true
  },
  loading: {
    type: Boolean
  }
})

// todo: paginate this with limit/offset
const filter = computed<LogsRequestFilter>(() => ({
  logs: {
    flow_run_id: {
      any_: [props.flowRunId]
    }
  }
}))

const options: SubscriptionOptions = {
  interval: props.loading ? 5000 : undefined
}
const subscription = subscribe(Logs.filter.bind(Logs), [filter.value], options)
const logs = computed<Log[]>(() => subscription.response.value ?? [])

watch(
  () => props.loading,
  () => subscription.unsubscribe()
)
</script>

<style>
.flow-run-logs-tabs-content {
  background-color: #fff;
}

.flow-run-logs-tabs-content__loading {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: var(--p-1);
}

.flow-run-logs-tabs-content__loader {
  /* loader needs to expose a prop */
  --loader-size: 25px !important;
  --loader-stroke-width: 5px !important;
  margin-right: var(--m-1);
}
</style>
