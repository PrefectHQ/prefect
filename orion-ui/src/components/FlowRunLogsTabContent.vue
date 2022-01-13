<template>
  <div class="flow-run-logs-tabs-content">
    <div class="flow-run-logs-tabs-content__header">
      <p class="flow-run-logs-tabs-content__span">Showing: Start to Now</p>
      <ButtonGroupInput v-model:value="levelFilter" :items="levels">
        <template #default="{ item }">
          {{ logLevelLabel(item) }}
        </template>
      </ButtonGroupInput>
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
            <Button
              v-show="levelFilter.length"
              class="ml-2"
              @click="clearFilters"
            >
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
  ButtonGroupInput,
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

const levels = [10, 20, 30, 40, 50]
const levelFilter = ref<number[]>([])

// todo: paginate this with limit/offset
const filter = computed<LogsRequestFilter>(() => {
  const level: Required<LogsRequestFilter>['logs']['level'] = {}

  if (levelFilter.value.length) {
    const minLevel = Math.min(...levelFilter.value)
    const maxLevel = Math.max(...levelFilter.value)

    if (minLevel > 0) {
      level.ge_ = minLevel
    }

    if (maxLevel < 50) {
      level.le_ = maxLevel
    }
  }

  return {
    logs: {
      flow_run_id: {
        any_: [props.flowRunId]
      },
      level
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
  levelFilter.value = []
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
  background-color: #fff;
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
