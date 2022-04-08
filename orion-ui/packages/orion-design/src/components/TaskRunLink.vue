<template>
  <template v-if="loaded">
    <span v-tooltip="taskRunName" class="task-run-link">
      <StateTypeIcon :type="taskRunStateType!" size="xs" colored />
      <span class="task-run-link__name">{{ taskRunName }}</span>
    </span>
  </template>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import StateTypeIcon from '@/components/StateTypeIcon.vue'
  import { taskRunsApiKey } from '@/services/TaskRunsApi'
  import { inject } from '@/utilities/inject'

  const taskRunsApi = inject(taskRunsApiKey)

  const props = defineProps({
    taskId: {
      type: String,
      required: true,
    },
  })

  const subscription = useSubscription(taskRunsApi.getTaskRun, [props.taskId])
  const loaded = computed(() => subscription.response !== undefined)
  const taskRunName = computed(() => subscription.response?.name)
  const taskRunStateType = computed(() => subscription.response?.stateType)
</script>

<style lang="scss">
.task-run-link {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
  min-width: 0;
}

.task-run-link__name {
  min-width: 0;
  margin-left: var(--m-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 600;
  /* color: var(--primary); */
}
</style>
