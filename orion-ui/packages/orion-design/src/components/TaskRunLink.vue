<template>
  <template v-if="task">
    <span v-tooltip="taskRunName" class="task-run-link">
      <StateTypeIcon :type="taskRunStateType!" size="xs" colored />
      <span class="task-run-link__name">{{ taskRunName }}</span>
    </span>
  </template>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue'
  import { TaskRun } from '..'
  import { TaskRuns } from '../services/TaskRunsApi'
  import StateTypeIcon from './StateTypeIcon.vue'

  const props = defineProps({
    taskId: {
      type: String,
      required: true,
    },
  })

  const task = ref<TaskRun | null>(null)
  const taskRunName = computed(() => task.value?.name)
  const taskRunStateType = computed(() => task.value?.stateType)

  task.value = await TaskRuns.getTaskRun(props.taskId)
</script>

<style lang="css">
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
