<template>
  <template v-if="loaded">
    <span v-tooltip="taskRunName" class="task-run-link">
      <StateTypeIcon :type="taskRunStateType!" size="xs" colored />
      <span class="task-run-link__name">{{ taskRunName }}</span>
    </span>
  </template>
</template>

<script lang="ts" setup>
  import { subscribe } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { taskRunsApi } from '../services/TaskRunsApi'
  import StateTypeIcon from './StateTypeIcon.vue'

  const props = defineProps({
    taskId: {
      type: String,
      required: true,
    },
  })

  const subscription = subscribe(taskRunsApi.getTaskRun.bind(taskRunsApi), [props.taskId])
  const loaded = computed(() => subscription.response.value)
  const taskRunName = computed(() => subscription.response.value?.name)
  const taskRunStateType = computed(() => subscription.response.value?.stateType)
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
