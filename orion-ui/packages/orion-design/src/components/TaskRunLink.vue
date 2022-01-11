<template>
  <template v-if="subscription.response">
    <a class="task-run-link">
      <StateTypeIcon :type="taskRunStateType!" colored />
      <span class="task-run-link__name">{{ taskRunName }}</span>
    </a>
  </template>
</template>

<script lang="ts" setup>
  import { subscribe } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { TaskRuns } from '../services/TaskRunsApi'
  import StateTypeIcon from './StateTypeIcon.vue'

  const props = defineProps({
    taskId: {
      type: String,
      required: true,
    },
  })

  const subscription = subscribe(TaskRuns.getTaskRun, [props.taskId])

  const taskRunName = computed(() => subscription.response.value?.name)
  const taskRunStateType = computed(() => subscription.response.value?.stateType)
</script>

<style lang="css">
.task-run-link {
  display: inline-flex;
  align-items: center;
}
</style>
