<template>
  <div class="flow-run-logs-tabs-content">
    <div class="flow-run-logs-tabs-content__header">
      <p class="flow-run-logs-tabs-content__span">Showing: Start to Now</p>
      <m-select
        v-model="levelFilter"
        :options="levelOptions"
        class="flow-run-logs-tabs-content__filter"
      />
    </div>
    <div class="flow-run-logs-tab-content__table">
      <div class="flow-run-logs-tab-content__table-header">
        <span
          class="
            flow-run-logs-tab-content__column
            flow-run-logs-tab-content__column--task
          "
        >
          Task run info
        </span>
        <span
          class="
            flow-run-logs-tab-content__column
            flow-run-logs-tab-content__column--level
          "
        >
          Level
        </span>
        <span
          class="
            flow-run-logs-tab-content__column
            flow-run-logs-tab-content__column--time
          "
        >
          Time
        </span>
        <span
          class="
            flow-run-logs-tab-content__column
            flow-run-logs-tab-content__column--message
          "
        >
          Message
        </span>
        <CopyButton :value="makeCsv" toast="Logs copied to clipboard">
          Copy Logs
        </CopyButton>
      </div>
      <FlowRunLogs v-show="!loading" :logs="logs">
        <template #empty>
          <p class="flow-run_logs-tab-content__empty">
            No logs to show.
            <Button v-show="levelFilter" class="ml-2" @click="clearFilters">
              Try clearing your filter
            </Button>
          </p>
        </template>
      </FlowRunLogs>
    </div>
    <template v-if="running || loading">
      <div class="flow-run-logs-tabs-content__loading">
        <m-loader :loading="true" class="flow-run-logs-tabs-content__loader" />
        <span v-show="running">Run in progress...</span>
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
import {
  Logs,
  LogsRequestFilter,
  FlowRunLogs,
  Log,
  logLevelLabel,
  formatDateTimeNumeric
} from '@prefecthq/orion-design'
import { subscribe } from '@prefecthq/vue-compositions'
import { SubscriptionOptions } from '@prefecthq/vue-compositions/src/subscribe/types'
import { computed, defineProps, ref, watch } from 'vue'
import CopyButton from './Global/CopyButton.vue'

const props = defineProps({
  flowRunId: {
    type: String,
    required: true
  },
  running: {
    type: Boolean
  }
})

const levelOptions = [
  { label: 'Critical only', value: 50 },
  { label: 'Error and above', value: 40 },
  { label: 'Warning and above', value: 30 },
  { label: 'Info and above', value: 20 },
  { label: 'Debug and above', value: 10 },
  { label: 'All log levels', value: 0 }
]
const levelFilter = ref<number>(0)

// todo: paginate this with limit/offset
const filter = computed<LogsRequestFilter>(() => {
  return {
    logs: {
      flow_run_id: {
        any_: [props.flowRunId]
      },
      level: {
        ge_: levelFilter.value
      }
    }
  }
})

const options: SubscriptionOptions = {
  interval: props.running ? 5000 : undefined
}
const subscription = subscribe(Logs.filter.bind(Logs), [filter], options)
const logs = computed<Log[]>(() => subscription.response.value ?? [])
const loading = computed<boolean>(() => subscription.loading.value ?? true)

const clearFilters = () => {
  levelFilter.value = 0
}

const makeCsv = (): string => {
  return logs.value
    .map((log) => {
      const level = logLevelLabel(log.level)
      const time = formatDateTimeNumeric(log.timestamp)

      return `${level}\t${time}\t${log.message}`
    })
    .join('\n')
}

watch(
  () => props.running,
  () => subscription.unsubscribe()
)
</script>

<style lang="scss">
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;
@use 'sass:map';

.flow-run-logs-tabs-content__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: var(--m-2) 0;
  flex-wrap: wrap;
  gap: var(--m-1);
}

.flow-run-logs-tabs-content__filter {
  width: 200px !important;
}

.flow-run-logs-tab-content__table-header {
  display: grid;
  justify-content: space-between;
  background-color: #fff;
  box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1);
  position: relative;
  z-index: 1;
  padding: var(--p-2);
  gap: var(--p-1);
  margin-bottom: var(--m-1);
  grid-template-areas: 'message copy';
  grid-template-columns: [message] 1fr [copy] 115px;

  @media screen and (min-width: map.get($breakpoints, 'md')) {
    grid-template-areas: 'task level time message copy';
    grid-template-columns: [task] 140px [level] 65px [time] 100px [message] 1fr [copy] 115px;
  }
}

.flow-run-logs-tab-content__column {
  font-weight: 600;
}

.flow-run-logs-tab-content__column--task,
.flow-run-logs-tab-content__column--level,
.flow-run-logs-tab-content__column--time {
  display: none;

  @media screen and (min-width: map.get($breakpoints, 'md')) {
    display: block;
  }
}

.flow-run-logs-tab-content__column--task {
  grid-area: task;
}

.flow-run-logs-tab-content__column--level {
  grid-area: level;
}

.flow-run-logs-tab-content__column--time {
  grid-area: time;
}

.flow-run-logs-tab-content__column--message {
  grid-area: message;
}

.flow-run-logs-tabs-content__span {
  font-size: 14px;
  font-family: 'input-sans';
  color: var(--grey-40);
  margin: 0;
}

.flow-run-logs-tab-content__table {
  border-radius: 4px;
  overflow: hidden;
  background-color: #fff;
  box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1);
}

.flow-run_logs-tab-content__empty {
  text-align: center;
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
