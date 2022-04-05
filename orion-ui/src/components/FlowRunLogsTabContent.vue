<template>
  <div class="flow-run-logs-tabs-content">
    <div class="flow-run-logs-tabs-content__header">
      <m-select
        v-model="levelFilter"
        :options="levelOptions"
        class="flow-run-logs-tabs-content__filter"
      />
      <CopyButton text :value="makeCsv" class="flow-run-logs__copy" toast="Logs copied to clipboard">
        Copy Logs
      </CopyButton>
    </div>
    <div class="flow-run-logs-tab-content__table">
      <div class="flow-run-logs-tab-content__table-header">
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
        <span
          class="
            flow-run-logs-tab-content__column
            flow-run-logs-tab-content__column-run
          "
        >
          Run name
        </span>
      </div>
      <div ref="logsRef" class="flow-run-logs-tab-content__logs">
        <FlowRunLogs :logs="logs">
          <template #empty>
            <p class="flow-run_logs-tab-content__empty">
              No logs to show.
              <m-button v-show="levelFilter" class="ml-2" @click="clearFilters">
                Try clearing your filter
              </m-button>
            </p>
          </template>
        </FlowRunLogs>
        <template v-if="running || loading">
          <div class="flow-run-logs-tabs-content__loading">
            <m-loader
              :loading="true"
              class="flow-run-logs-tabs-content__loader"
            />
            <span v-show="running">Run in progress...</span>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import {
    LogsRequestFilter,
    FlowRunLogs,
    Log,
    logLevelLabel,
    formatDateTimeNumeric,
    CopyButton
  } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { SubscriptionOptions } from '@prefecthq/vue-compositions/src/subscribe/types'
  import { computed, nextTick, ref, watch } from 'vue'
  import { logsApi } from '@/services/logsApi'

  const props = defineProps({
    flowRunId: {
      type: String,
      required: true,
    },
    running: {
      type: Boolean,
    },
  })

  const logsRef = ref<HTMLDivElement>()

  const levelOptions = [
    { label: 'Critical only', value: 50 },
    { label: 'Error and above', value: 40 },
    { label: 'Warning and above', value: 30 },
    { label: 'Info and above', value: 20 },
    { label: 'Debug and above', value: 10 },
    { label: 'All log levels', value: 0 },
  ]
  const levelFilter = ref<number>(0)

  // todo: paginate this with limit/offset
  const filter = computed<LogsRequestFilter>(() => {
    return {
      logs: {
        flow_run_id: {
          any_: [props.flowRunId],
        },
        level: {
          ge_: levelFilter.value,
        },
      },
    }
  })

  const options: SubscriptionOptions = {
    interval: props.running ? 5000 : undefined,
  }
  const subscription = useSubscription(logsApi.getLogs, [filter], options)
  const logs = computed<Log[]>(() => subscription.response ?? [])
  const loading = computed<boolean>(() => subscription.loading ?? true)

  const clearFilters = (): void => {
    levelFilter.value = 0
  }

  const updateScrollPosition = (): void => {
    if (!logsRef.value) {
      return
    }

    const div = logsRef.value
    const hasScrolled = div.scrollTop > 0
    const atBottom = div.scrollTop + div.offsetHeight === div.scrollHeight

    if (hasScrolled && atBottom) {
      nextTick(() => {
        div.scrollTop = div.scrollHeight
      })
    }
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
    () => subscription.unsubscribe(),
  )

  watch(
    () => subscription.response,
    () => updateScrollPosition(),
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
    grid-template-areas: 'level time message task';
    grid-template-columns: [level] 65px [time] 108px [message] 1fr [task] 140px;
  }
}

.flow-run-logs-tab-content__column {
  font-weight: 600;
}

.flow-run-logs-tab-content__column--level,
.flow-run-logs-tab-content__column--time,
.flow-run-logs-tab-content__column-run {
  display: none;

  @media screen and (min-width: map.get($breakpoints, 'md')) {
    display: block;
  }
}

.flow-run-logs-tab-content__column-run {
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

.flow-run-logs-tab-content__logs {
  height: 300px;
  overflow-y: auto;
  position: relative;
}

.flow-run-logs__copy {
  border: none;
  background-color: inherit;
  color: #024dfd;
  cursor: pointer;
  font-weight: 600;
}
</style>


