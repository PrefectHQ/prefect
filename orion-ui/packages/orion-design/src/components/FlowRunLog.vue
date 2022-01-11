<template>
  <div class="flow-run-log">
    <template v-if="log.taskRunId">
      <div class="flow-run-log__task">
        <TaskRunLink :task-id="log.taskRunId" />
      </div>
    </template>
    <LogLevelLabel :level="log.level" class="flow-run-log__level" />
    <span class="flow-run-log__time" :class="classes.time">{{ time }}</span>
    <div class="flow-run-log__details">
      <span class="flow-run-log__message">{{ log.message }}</span>
      <CopyButton :value="log.message" class="flow-run-log__copy" toast="Copied message to clipboard" icon-only />
    </div>
  </div>
</template>

<script lang="ts">
  import CopyButton from '@/components/Global/CopyButton.vue'
  import { snakeCase } from '@/utilities/strings'
  import { defineComponent, PropType } from 'vue'
  import { formatTimeNumeric, LogLevel } from '..'
  import { Log } from '../models'
  import LogLevelLabel from './LogLevelLabel.vue'
  import TaskRunLink from './TaskRunLink.vue'

  export default defineComponent({
    name: 'FlowRunLog',
    components: {
      LogLevelLabel,
      TaskRunLink,
      CopyButton,
    },

    expose: [],
    props: {
      log: {
        type: Object as PropType<Log>,
        required: true,
      },
    },

    computed: {
      classes: function() {
        return {
          time: [`flow-run-log__time--${snakeCase(LogLevel.GetLabel(this.log.level))}`],
        }
      },

      time: function() {
        return formatTimeNumeric(this.log.timestamp)
      },
    },
  })
</script>

<style lang="scss">
.flow-run-log {
  display: grid;
  grid-template-columns: [task] 140px [level] 65px [time] 100px [message] 1fr;
  gap: var(--p-1);
  font-size: 13px;
  padding: 0 var(--p-1);
}

.flow-run-log__task {
  grid-column: task;
  background-color: #F9FAFD;
  display: flex;
  align-items: flex-start;
  padding: 0 var(--p-1);
}

.flow-run-log__level {
  margin-top: 3px;
  grid-column: level;
}

.flow-run-log__time {
  padding-top: 1px;
  font-family: 'input-sans';
  text-align: center;
  grid-column: time;
  color: var(--log-level-info);
}

.flow-run-log__time--error {
  color: var(--log-level-error);
}

.flow-run-log__time--critical {
  color: var(--log-level-critical);
}

.flow-run-log__details {
  margin: 0;
  font-family: 'input-sans';
  border: 1px solid transparent;
  border-radius: 4px;
  grid-column: message;
  padding: 0 var(--p-1);
  display: flex;

  &:hover {
    background-color: #F9FAFD;
    border-color: #ACBBF3;

    .flow-run-log__copy {
      opacity: 1;
    }
  }
}

.flow-run-log__message {
  flex-grow: 1;
}

.flow-run-log__copy {
  align-self: flex-start;
  padding: 2px !important; // copy-button is scoped...
  opacity: 0;
}
</style>