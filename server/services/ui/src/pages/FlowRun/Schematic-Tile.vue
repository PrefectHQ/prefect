<script>
import CardTitle from '@/components/Card-Title'
import DurationSpan from '@/components/DurationSpan'
import SchematicFlow from '@/components/Schematics/Schematic-Flow'
import moment from '@/utils/moment'
import { STATE_COLORS } from '@/utils/states'

export default {
  filters: {
    typeClass: val => val.split('.').pop()
  },
  components: {
    CardTitle,
    DurationSpan,
    SchematicFlow
  },
  data() {
    return {
      expanded: true,
      runs: null,
      task: null,
      tasks: [],
      flowRunName: ''
    }
  },
  watch: {
    $route(val) {
      if (!val.query.schematic) return (this.task = null)
      let runs = this.tasks.filter(task => task.task.id == val.query.schematic)

      let index =
        runs.length > 1 ? runs.findIndex(task => task.state == 'Mapped') : 0

      this.task = runs.splice(index, 1)[0]
      this.runs = runs
    },
    tasks() {
      if (!this.$route.query.schematic) return (this.task = null)

      let runs = this.tasks.filter(
        task => task.task.id == this.$route.query.schematic
      )

      let index =
        runs.length > 1 ? runs.findIndex(task => task.state == 'Mapped') : 0

      this.task = runs.splice(index, 1)[0]
      this.runs = runs
    }
  },
  methods: {
    formatTime(timestamp) {
      if (!timestamp) throw new Error('Did not recieve a timestamp')

      let timeObj = moment(timestamp).tz(this.timezone),
        shortenedTz = moment()
          .tz(this.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone)
          .zoneAbbr()
      return `${
        timeObj ? timeObj.format('h:mma') : moment(timestamp).format('h:mma')
      } ${shortenedTz}`
    },
    formatDate(timestamp) {
      if (!timestamp) throw new Error('Did not receive a timestamp')

      let timeObj = moment(timestamp).tz(this.timezone)
      return `${
        timeObj
          ? timeObj.format('D MMMM YYYY')
          : moment(timestamp).format('D MMMM YYYY')
      }`
    },
    runStyle(state) {
      return {
        'border-left': state
          ? `0.5rem solid ${
              this.disabled
                ? this.hex2RGBA(STATE_COLORS[state])
                : STATE_COLORS[state]
            } !important`
          : ''
      }
    }
  },
  apollo: {
    flowRun: {
      query: require('@/graphql/Schematics/flow-run.gql'),
      variables() {
        return {
          id: this.$route.params.id
        }
      },
      skip() {
        return !this.$route.params.id
      },
      update(data) {
        if (data.flow_run && data.flow_run.length) {
          this.flowRunName = data.flow_run[0].name
          this.tasks = data.flow_run[0].task_runs
          return data.flow_run[0]
        } else {
          this.tasks = []
        }
      },
      pollInterval: 1000
    }
  }
}
</script>

<template>
  <v-card class="pa-2 mt-2" tile>
    <CardTitle title="Flow Run Schematic" icon="account_tree">
      <div v-if="flowRun" slot="badge" class="body-2">
        <v-chip
          class="body-2 white--text font-weight-bold badge"
          color="accentOrange"
        >
          Beta
        </v-chip>

        <span class="vertical-divider mx-4"></span>

        <span>
          Run State:
          <span
            class="font-weight-bold"
            :style="{ color: `var(--v-${flowRun.state}-base)` }"
          >
            {{ flowRun.state }}
          </span>
        </span>

        <span class="ml-4">
          Duration:
          <span v-if="flowRun.duration" class="font-weight-black">
            {{ flowRun.duration | duration }}
          </span>
          <span v-else-if="flowRun.start_time" class="font-weight-black">
            <DurationSpan :start-time="flowRun.start_time" />
          </span>
        </span>
      </div>
    </CardTitle>

    <v-card-text class="full-height position-relative">
      <SchematicFlow :tasks="tasks" />

      <!-- Could probably componentize this at some point -->
      <v-card v-if="task" class="task-tile position-absolute" tile>
        <v-list-item
          class="py-2 pr-2 pl-3"
          dense
          :to="{ name: 'task-run', params: { id: task.id } }"
          :style="runStyle(task.state)"
        >
          <v-list-item-content class="my-0 py-0">
            <v-list-item-subtitle class="caption mb-0">
              Task Run
            </v-list-item-subtitle>
            <v-list-item-title>
              {{ flowRunName }} - {{ task.task.name
              }}<span v-if="task.map_index > -1"> ({{ task.map_index }})</span>
            </v-list-item-title>
            <v-list-item-subtitle class="caption">
              <v-tooltip top>
                <template v-slot:activator="{ on }">
                  <span v-on="on">
                    <span :class="`${task.state}--text`">
                      {{ task.state }}
                    </span>
                    - {{ formatTime(task.state_timestamp) }}
                  </span>
                </template>
                <span>
                  {{ formatDate(task.state_timestamp) }}
                </span>
              </v-tooltip>
            </v-list-item-subtitle>
          </v-list-item-content>
          <v-list-item-avatar class="body-2">
            <v-icon class="grey--text text--darken-2">
              arrow_right
            </v-icon>
          </v-list-item-avatar>
        </v-list-item>

        <v-list-item
          dense
          class="py-2 pr-2 pl-5"
          :to="{ name: 'task', params: { id: task.task.id } }"
        >
          <v-list-item-content class="my-0 py-0">
            <v-list-item-subtitle class="caption mb-0">
              Task
            </v-list-item-subtitle>
            <v-list-item-title>
              {{ task.task.name }}
            </v-list-item-title>
          </v-list-item-content>

          <v-list-item-avatar class="body-2">
            <v-icon class="grey--text">
              arrow_right
            </v-icon>
          </v-list-item-avatar>
        </v-list-item>

        <v-divider></v-divider>

        <v-card-text class="pb-0 pl-3 pr-2 caption">
          <v-row>
            <v-col cols="12" class="pb-0 pt-0">
              <span class="black--text">Task Run State Message:</span>
            </v-col>
            <v-col cols="12" class="pt-0">
              {{ task.state_message }}
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="6" class="pt-0">
              <span class="black--text">Max retries:</span>
            </v-col>
            <v-col cols="6" class="text-right pt-0">
              {{ task.task.max_retries }}
            </v-col>
          </v-row>

          <v-row v-if="task.task.max_retries > 0">
            <v-col cols="6" class="pt-0">
              <span class="black--text">Retry delay:</span>
            </v-col>
            <v-col cols="6" class="text-right pt-0">
              {{ task.task.retry_delay }}
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="6" class="pt-0">
              <span class="black--text">Class:</span>
            </v-col>
            <v-col cols="6" class="text-right pt-0">
              {{ task.task.type | typeClass }}
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="6" class="pt-0">
              <span class="black--text">Trigger:</span>
            </v-col>
            <v-col cols="6" class="text-right pt-0">
              {{ task.task.trigger | typeClass }}
            </v-col>
          </v-row>
        </v-card-text>

        <v-card-actions v-if="runs && runs.length > 0" class="px-0 py-0">
          <v-list dense style="width: 100%;" class="py-0">
            <v-list-group v-model="expanded" no-action dense value="true">
              <template v-slot:activator>
                <v-list-item-content class="pa-0">
                  <v-list-item-title class="body-2 d-flex align-end">
                    <v-icon class="black--text mr-6" small>trending_up</v-icon>
                    <span class="font-weight-black mr-1">
                      {{ runs.length }}
                    </span>
                    Mapped Run{{ runs.length > 1 ? 's' : '' }}
                  </v-list-item-title>
                </v-list-item-content>
              </template>

              <template v-slot:appendIcon>
                <v-list-item-avatar class="mr-0">
                  <v-icon>arrow_drop_down</v-icon>
                </v-list-item-avatar>
              </template>

              <v-divider></v-divider>

              <v-list-item-group class="mapped-tasks-container">
                <v-lazy
                  v-for="run in runs"
                  :key="run.id"
                  :options="{
                    threshold: 0.75
                  }"
                  min-height="40px"
                  transition="fade"
                >
                  <v-list-item
                    dense
                    two-line
                    class="px-2 py-1"
                    :to="{ name: 'task-run', params: { id: run.id } }"
                    :style="runStyle(run.state)"
                  >
                    <v-tooltip bottom>
                      <template v-slot:activator="{ on }">
                        <v-list-item-content v-on="on">
                          <v-list-item-title>
                            {{ run.state }}
                          </v-list-item-title>
                          <v-list-item-subtitle class="caption">
                            {{ run.state_message }}
                          </v-list-item-subtitle>
                        </v-list-item-content>
                      </template>
                      <span>
                        {{ run.state_message }}
                      </span>
                    </v-tooltip>
                    <v-list-item-avatar
                      class="caption"
                      style="min-width: 85px;"
                    >
                      {{ formatTime(run.state_timestamp) }}
                    </v-list-item-avatar>
                  </v-list-item>
                </v-lazy>
              </v-list-item-group>
            </v-list-group>
          </v-list>
        </v-card-actions>
      </v-card>
    </v-card-text>
  </v-card>
</template>

<style lang="scss" scoped>
.full-height {
  min-height: 67vh;
}

.mapped-tasks-container {
  max-height: 30vh;
  overflow: scroll;
}

.task-tile {
  right: 1rem;
  top: 1rem;
  width: 33%;
}

.position-relative {
  position: relative;
}

.position-absolute {
  position: absolute;
}

.vertical-divider {
  border-left: 0.5px solid rgba(0, 0, 0, 0.26);
  border-right: 0.5px solid rgba(0, 0, 0, 0.26);
  height: 75%;
}
</style>
