<script>
import CardTitle from '@/components/Card-Title'
import DurationSpan from '@/components/DurationSpan'

export default {
  filters: {
    typeClass: val => val.split('.').pop()
  },
  components: {
    CardTitle,
    DurationSpan
  },
  props: {
    taskRun: {
      type: Object,
      default: () => {}
    }
  },
  data() {
    return {}
  },
  computed: {
    filteredParams() {
      return {
        [this.taskRun.task.name]: this.taskRun.flow_run.parameters[
          this.taskRun.task.name
        ]
      }
    }
  }
}
</script>

<template>
  <v-card class="pa-2" tile>
    <v-system-bar :color="taskRun.state" :height="5" absolute>
      <!-- We should include a state icon here when we've got those -->
      <!-- <v-icon>{{ flowRun.state }}</v-icon> -->
    </v-system-bar>

    <CardTitle
      :title="taskRun.task.name"
      icon="done_all"
      :subtitle="taskRun.state"
      :params="{ name: 'task', params: { id: taskRun.task.id } }"
    />

    <v-list-item
      dense
      two-line
      :to="{ name: 'flow-run', params: { id: taskRun.flow_run.id } }"
      class="px-0"
    >
      <v-list-item-avatar class="mr-2">
        <v-icon small>trending_up</v-icon>
      </v-list-item-avatar>
      <v-list-item-content>
        <span class="caption mb-0">
          Flow Run
        </span>
        <v-list-item-title class="body-2">
          <span>{{ taskRun.flow_run.name }}</span>
        </v-list-item-title>
        <v-list-item-title class="caption">
          <span :class="`${taskRun.flow_run.state}--text`">
            {{ taskRun.flow_run.state }}
          </span>
        </v-list-item-title>
      </v-list-item-content>
    </v-list-item>

    <v-card-text class="pl-12 py-0">
      <v-list-item dense class="px-0">
        <v-list-item-content v-if="taskRun.state_message">
          <v-list-item-subtitle class="caption">
            Last State Message
          </v-list-item-subtitle>
          <div class="subtitle-2">
            <v-tooltip top>
              <template v-slot:activator="{ on }">
                <span class="caption" v-on="on">
                  [{{ taskRun.state_timestamp | displayTime }}]:
                </span>
              </template>
              <div>
                {{ taskRun.state_timestamp | displayTimeDayMonthYear }}
              </div>
            </v-tooltip>
            {{ taskRun.state_message }}
          </div>
        </v-list-item-content>
      </v-list-item>

      <v-list-item dense class="pa-0">
        <v-list-item-content>
          <v-list-item-subtitle class="caption">
            <v-row v-if="taskRun.start_time" no-gutters>
              <v-col cols="6">
                Started
              </v-col>
              <v-col cols="6" class="text-right font-weight-bold">
                <v-tooltip top>
                  <template v-slot:activator="{ on }">
                    <span v-on="on">
                      {{
                        taskRun.start_time
                          ? taskRun.start_time
                          : taskRun.scheduled_start_time | displayTime
                      }}
                    </span>
                  </template>
                  <div>
                    {{
                      taskRun.start_time
                        ? taskRun.start_time
                        : taskRun.scheduled_start_time | displayTimeDayMonthYear
                    }}
                  </div>
                </v-tooltip>
              </v-col>
            </v-row>
            <v-row v-if="taskRun.end_time" no-gutters>
              <v-col cols="6">
                Ended
              </v-col>
              <v-col cols="6" class="text-right font-weight-bold">
                <v-tooltip top>
                  <template v-slot:activator="{ on }">
                    <span v-on="on">
                      {{ taskRun.end_time | displayTime }}
                    </span>
                  </template>
                  <div>
                    {{ taskRun.end_time | displayTimeDayMonthYear }}
                  </div>
                </v-tooltip>
              </v-col>
            </v-row>
            <v-row v-if="taskRun.start_time" no-gutters>
              <v-col cols="6">
                Duration
              </v-col>
              <v-col cols="6" class="text-right font-weight-bold">
                <span v-if="taskRun.duration">
                  {{ taskRun.duration | duration }}
                </span>
                <DurationSpan
                  v-else-if="taskRun.start_time"
                  :start-time="taskRun.start_time"
                />
                <span v-else>
                  <v-skeleton-loader type="text"></v-skeleton-loader>
                </span>
              </v-col>
            </v-row>
            <v-row v-if="taskRun.heartbeat" no-gutters>
              <v-col cols="6">
                Heartbeat
              </v-col>
              <v-col cols="6" class="text-right font-weight-bold">
                <v-tooltip top>
                  <template v-slot:activator="{ on }">
                    <span v-on="on">
                      {{ taskRun.heartbeat | displayTime }}
                    </span>
                  </template>
                  <div>
                    {{ taskRun.heartbeat | displayTimeDayMonthYear }}
                  </div>
                </v-tooltip>
              </v-col>
            </v-row>

            <v-row no-gutters>
              <v-col cols="6">
                Class
              </v-col>
              <v-col cols="6" class="text-right font-weight-bold">
                {{ taskRun.task.type | typeClass }}
              </v-col>
            </v-row>

            <v-row no-gutters>
              <v-col cols="6">
                Trigger
              </v-col>
              <v-col cols="6" class="text-right font-weight-bold">
                {{ taskRun.task.trigger | typeClass }}
              </v-col>
            </v-row>
          </v-list-item-subtitle>
        </v-list-item-content>
      </v-list-item>

      <v-list-item
        v-if="$options.filters.typeClass(taskRun.task.type) == 'Parameter'"
        dense
        two-line
        class="px-0"
      >
        <v-list-item-content>
          <v-list-item-subtitle>
            <div class="caption mb-0">
              Parameter:
            </div>

            <code class="mt-3 pa-3 no-before-after-content code-custom"
              >{{ filteredParams }}
            </code>
          </v-list-item-subtitle>
        </v-list-item-content>
      </v-list-item>
    </v-card-text>
  </v-card>
</template>

<style lang="scss" scoped>
a {
  text-decoration: none !important;
}

.code-custom {
  background-color: #fafafa;
  box-shadow: none;
  color: #0073df;
  font-size: 0.9em;
}

.no-before-after-content {
  &::before,
  &::after {
    content: '' !important;
  }
}
</style>
