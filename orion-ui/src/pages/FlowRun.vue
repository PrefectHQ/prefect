<template>
  <div class="flow-run">
    Flow run {{ flowRunId }}
  </div>

  <div>
    Logs
  </div>

  <div v-for="log in logs" :key="log.id">
    {{ logs }}
  </div>

  <PButton @click="nextLogsPage">
    Next log
  </PButton>
</template>

<script lang="ts" setup>
  import { useRouteParam, Log, LogsRequestFilter } from '@prefecthq/orion-design'
  import { PButton } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { SubscriptionOptions } from '@prefecthq/vue-compositions/src/subscribe/types'
  import { computed, ref } from 'vue'
  import { logsApi } from '@/services/logsApi'

  const flowRunId = useRouteParam('id')
  const levelOptions = [
    { label: 'Critical only', value: 50 },
    { label: 'Error and above', value: 40 },
    { label: 'Warning and above', value: 30 },
    { label: 'Info and above', value: 20 },
    { label: 'Debug and above', value: 10 },
    { label: 'All log levels', value: 0 },
  ] as const

  const levelFilter = ref<typeof levelOptions[number]['value']>(0)

  const logsOffset = ref<number>(0)
  const logsLimit = ref<number>(1)
  const nextLogsPage = (): void => {
    logsOffset.value +=logsLimit.value
  }
  const filter = computed<LogsRequestFilter>(() => {
    return {
      logs: {
        flow_run_id: {
          any_: [flowRunId.value],
        },
        level: {
          ge_: levelFilter.value,
        },
      },
      offset: logsOffset.value,
      limit: logsLimit.value,
    }
  })

  const options: SubscriptionOptions = { interval:  5000 }

  const subscription = useSubscription(logsApi.getLogs, [filter], options)
  const logs = computed<Log[]>(() => subscription.response ?? [])
</script>

<style>
.flow-run {}
</style>