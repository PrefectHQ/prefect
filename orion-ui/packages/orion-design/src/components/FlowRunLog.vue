<template>
  <div>
    <p>{{ log }}</p>
    <template v-if="log.taskRunId">
      <TaskRunLink :task-id="log.taskRunId" />
    </template>
    <LogLevelLabel :level="log.level" />
    <p>{{ log.message }}</p>
  </div>
</template>

<script lang="ts">
  import { defineComponent, PropType } from 'vue'
  import { Log } from '../models'
  import LogLevelLabel from './LogLevelLabel.vue'
  import TaskRunLink from './TaskRunLink.vue'

  export default defineComponent({
    name: 'FlowRunLog',
    components: {
      LogLevelLabel,
      TaskRunLink,
    },

    expose: [],
    props: {
      log: {
        type: Object as PropType<Log>,
        required: true,
      },
    },
  })
</script>