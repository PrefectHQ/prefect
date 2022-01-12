<template>
  <div class="flow-run-logs-tabs-content">
    <div class="flow-run-logs-tabs-content__header">
      <p class="flow-run-logs-tabs-content__span">Showing: Start to Now</p>
      <ButtonGroupInput
        v-model:value="levelFilter"
        :items="[10, 20, 30, 40, 50]"
      >
        <template #default="{ item }">
          {{ LogLevel.GetLabel(item) }}
        </template>
      </ButtonGroupInput>
    </div>
    <div class="flow-run-logs-tab-content__table">
      <FlowRunLogs :logs="logs">
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
    <template v-if="loading">
      <div class="flow-run-logs-tabs-content__loading">
        <m-loader loading class="flow-run-logs-tabs-content__loader" />
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
  Log,
  LogLevel,
  ButtonGroupInput
} from '@prefecthq/orion-design'
import { subscribe } from '@prefecthq/vue-compositions'
import { SubscriptionOptions } from '@prefecthq/vue-compositions/src/subscribe/types'
import { computed, defineProps, reactive, ref, watch } from 'vue'

const props = defineProps({
  flowRunId: {
    type: String,
    required: true
  },
  loading: {
    type: Boolean
  }
})

const levelFilter = ref<number[]>([])

// todo: paginate this with limit/offset
const filter = computed<LogsRequestFilter>(() => {
  const level: Required<LogsRequestFilter>['logs']['level'] = {}
  const minLevel = Math.min(...levelFilter.value)
  const maxLevel = Math.max(...levelFilter.value)

  if (levelFilter.value.length) {
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
  interval: props.loading ? 5000 : undefined
}
const subscription = subscribe(Logs.filter.bind(Logs), [filter], options)
const logs = computed<Log[]>(() => subscription.response.value ?? [])

const clearFilters = () => {
  levelFilter.value = []
}

watch(
  () => props.loading,
  () => subscription.unsubscribe()
)
</script>

<style>
.flow-run-logs-tabs-content {
}

.flow-run-logs-tabs-content__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: var(--m-2) 0;
  flex-wrap: wrap;
  gap: var(--m-1);
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
