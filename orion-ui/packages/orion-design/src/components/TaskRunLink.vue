<template>
  <template v-if="task">
    <a class="task-run-link">
      <StateTypeIcon :type="taskRunStateType!" colored />
      <span class="task-run-link__name">{{ taskRunName }}</span>
    </a>
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
}
</style>
