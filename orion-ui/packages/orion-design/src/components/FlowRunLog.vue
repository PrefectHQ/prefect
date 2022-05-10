<template>
  <div class="flow-run-log">
    <LogLevelLabel :level="log.level" class="flow-run-log__level" />
    <span v-tooltip="dateTime" class="flow-run-log__time" :class="classes.time">{{ time }}</span>
    <template v-if="log.taskRunId">
      <div class="flow-run-log__task">
        <TaskRunLink :task-id="log.taskRunId" />
      </div>
    </template>
    <div class="flow-run-log__details">
      <span class="flow-run-log__message">{{ log.message }}</span>
      <CopyButton :value="log.message" label="" class="flow-run-log__copy" toast="Copied message to clipboard" />
    </div>
  </div>
</template>

<script lang="ts">
  import { defineComponent, PropType } from 'vue'
  import CopyButton from '@/components/CopyButton.vue'
  import LogLevelLabel from '@/components/LogLevelLabel.vue'
  import TaskRunLink from '@/components/TaskRunLink.vue'
  import { Log } from '@/models/Log'
  import { formatDateTimeNumericInTimeZone, formatTimeNumericInTimeZone } from '@/utilities/dates'
  import { logLevelLabel } from '@/utilities/logs'
  import { snakeCase } from '@/utilities/strings'

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
          time: [`flow-run-log__time--${snakeCase(logLevelLabel(this.log.level))}`],
        }
      },

      time: function() {
        return formatTimeNumericInTimeZone(this.log.timestamp)
      },

      dateTime: function() {
        return formatDateTimeNumericInTimeZone(this.log.timestamp)
      },
    },
  })
</script>

<style lang="scss">
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;
@use 'sass:map';

.flow-run-log {
  display: grid;
  gap: var(--p-1);
  font-size: 13px;
  padding: var(--p-1);
  padding-bottom: 0;
  display: flex;
  flex-direction: column;

  + .flow-run-log {
    border-top: 1px solid var(--grey-20);
  }

  @media screen and (min-width: map.get($breakpoints, 'sm')) {
    display: grid;
    grid-template-columns: 100px 1fr;
    grid-template-areas:
      "level   task"
      "time    ."
      "message message";
  }

  @media screen and (min-width: map.get($breakpoints, 'md')) {
    grid-template-areas: "level time message task";
    grid-template-columns: [level] 65px [time] 108px [message] 1fr [task] 140px;
    padding: 0 var(--p-2);

    + .flow-run-log {
      border: 0;
    }
  }
}

.flow-run-log__task {
  grid-area: task;
  background-color: #F9FAFD;
  display: flex;
  align-items: flex-start;
  padding: 0 var(--p-1);
  max-width: 100%;
  min-width: 0;
  margin-right: auto;
  user-select: none;

  @media screen and (min-width: map.get($breakpoints, 'sm')) {
    margin-right: unset;
    margin-left: auto;
  }

  @media screen and (min-width: map.get($breakpoints, 'md')) {
    margin-left: unset;
  }
}

.flow-run-log__level {
  user-select: none;
  margin-top: 3px;
  grid-area: level;
}

.flow-run-log__time {
  padding-top: 1px;
  font-family: var(--font-secondary);
  grid-area: time;
  color: var(--log-level-info);
  text-align: left;
}

.flow-run-log__time--error {
  color: var(--log-level-error);
}

.flow-run-log__time--critical {
  color: var(--log-level-critical);
}

.flow-run-log__details {
  margin: 0;
  font-family: var(--font-secondary);
  border: 1px solid transparent;
  border-radius: 4px;
  grid-area: message;
  display: flex;
  white-space: pre-wrap;

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