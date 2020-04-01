<script>
import { STATE_COLORS, STATE_TYPES } from '@/utils/states'
import { mapMutations } from 'vuex'
import debounce from 'lodash.debounce'
import moment from 'moment-timezone'
import FullPagination from '@/components/FullPagination'

export default {
  components: { FullPagination },
  props: {
    flowRunId: {
      required: true,
      type: String
    }
  },
  data() {
    return {
      chartRenderColorIndex: 0,
      colors: STATE_COLORS,
      flowRun: null,
      limit: 10,
      page: 1,
      presentStates: {},
      selectedActivityStateFilter: [],
      sortOrder: 'desc',
      tableSearchInput: null
    }
  },
  computed: {
    tableSearchFormatted() {
      if (!this.tableSearchInput) return null
      return `%${this.tableSearchInput}%`
    },
    chartData() {
      const series = [
        {
          name: this.flowRun.flow.name,
          data: this.flowRun.task_runs.map(taskRun => {
            // We handle tasks that don't start by not showing this chart at all
            // if the task run has a start time and end time
            if (taskRun.start_time) {
              return {
                x: this.taskRunNameFormatter(taskRun),
                y: [
                  new Date(taskRun.start_time).getTime(),
                  taskRun.end_time
                    ? new Date(taskRun.end_time).getTime()
                    : new Date().getTime()
                ]
              }
            }
            // if the task is running or didn't get an start_time or end_time
            return {
              x: this.taskRunNameFormatter(taskRun),
              y: [
                new Date(this.flowRun.start_time).getTime(),
                this.flowRun.end_time
                  ? new Date(this.flowRun.end_time).getTime()
                  : new Date().getTime()
              ]
            }
          })
        }
      ]
      return {
        series,
        options: {
          chart: {
            events: {
              dataPointSelection: this.handleDataPointSelection,
              dataPointMouseEnter: this.cursorPointer
            },
            toolbar: {
              show: false
            }
          },
          colors: this.flowRun.task_runs.map(task => STATE_COLORS[task.state]),
          plotOptions: {
            bar: {
              horizontal: true
            }
          },
          tooltip: {
            y: {
              formatter: this.tooltipFormatter
            },
            x: {
              formatter: this.tooltipFormatter
            },
            z: {
              formatter: this.tooltipFormatter
            }
          },
          xaxis: {
            type: 'datetime',
            labels: {
              formatter: this.formatDate
            }
          },
          yaxis: {
            min: new Date(this.flowRun.start_time).getTime(),
            max: this.flowRun.end_time
              ? new Date(this.flowRun.end_time).getTime()
              : new Date().getTime()
          }
        }
      }
    },
    noChartMessage() {
      if (!this.flowRun || this.flowRun.start_time) return null
      if (
        !this.flowRun.start_time &&
        STATE_TYPES[this.flowRun.state] === 'Pending'
      ) {
        return "Flow Run Hasn't Started Yet"
      } else if (
        !this.flowRun.start_time &&
        STATE_TYPES[this.flowRun.state] === 'Finished'
      ) {
        return 'Flow Run Did Not Start Successfully'
      }
      return null
    },
    offset() {
      return this.limit * (this.page - 1)
    }
  },
  watch: {
    selectedActivityStateFilter() {
      this.page = 1
    }
  },
  methods: {
    ...mapMutations('sideDrawer', ['openDrawer']),
    handleChangePagination(newLimit) {
      this.limit = newLimit
    },
    handleSort() {
      if (this.sortOrder === 'asc') {
        this.sortOrder = 'desc'
      } else {
        this.sortOrder = 'asc'
      }
    },
    handleDataPointSelection(event, chartContext, config) {
      let taskRun = this.flowRun.task_runs[config.dataPointIndex]

      this.openDrawer({
        type: 'SideDrawerTaskRun',
        title: 'Task Run Details',
        props: {
          id: taskRun.id
        }
      })
    },
    cursorPointer(event) {
      event.target.style.cursor = 'pointer'
    },
    formatDate(value) {
      if (this.timezone) {
        return moment(value)
          .tz(this.timezone)
          .format('LTS')
      }
      return moment(value).format('LTS')
    },
    taskRunNameFormatter(taskRun) {
      if (typeof taskRun.map_index === 'number' && taskRun.map_index > -1) {
        return `${taskRun.task.name} (${taskRun.map_index})`
      }
      return taskRun.task.name
    },
    tooltipFormatter(value) {
      if (typeof value === 'number') {
        return this.formatDate(value)
      }
      return value
    },
    handleTableSearchInput: debounce(function(e) {
      this.tableSearchInput = e
    }, 300)
  },
  apollo: {
    flowRun: {
      query: require('@/graphql/FlowRun/flow-run.gql'),
      variables() {
        let taskRunStates
        if (this.selectedActivityStateFilter.length) {
          taskRunStates = this.selectedActivityStateFilter
        } else {
          taskRunStates = null
        }

        return {
          taskRunStates,
          taskName: this.tableSearchFormatted,
          id: this.flowRunId,
          limit: this.limit,
          offset: this.offset,
          sort: this.sortOrder
        }
      },
      pollInterval: 1000,
      update: data => data.flow_run_by_pk
    }
  }
}
</script>
<template>
  <v-card v-if="flowRun" class="ma-0" flat>
    <v-list-item dense class="px-0 mt-2">
      <v-list-item-avatar class="mr-2">
        <v-icon color="black">
          bar_chart
        </v-icon>
      </v-list-item-avatar>
      <v-list-item-content>
        <v-list-item-title class="title">
          <v-row no-gutters class="d-flex align-center">
            <v-col cols="9"><div>Task Runs</div></v-col>
            <v-col cols="3">
              <v-text-field
                class="mx-2 task-run-search"
                :class="{ 'my-1': $vuetify.breakpoint.mdAndUp }"
                hide-details
                label="Task Name"
                prepend-inner-icon="search"
                dense
                solo
                flat
                single-line
                @input="handleTableSearchInput"
              />
            </v-col>
          </v-row>
        </v-list-item-title>
      </v-list-item-content>
    </v-list-item>

    <v-divider class="ml-12"></v-divider>

    <v-subheader
      v-if="!noChartMessage"
      color="white"
      class="d-block subtitle-2 black--text medium pt-2"
    >
      <div>
        <v-btn-toggle v-model="selectedActivityStateFilter" multiple>
          <v-btn
            v-for="(taskRun, index) in flowRun.task_run_states"
            :key="index"
            active-class="grey"
            text
            class="text-none mx-1"
            :value="taskRun.state"
            outlined
          >
            <v-icon small left :color="colors[taskRun.state]">
              brightness_1
            </v-icon>
            {{ taskRun.state }}
          </v-btn>
        </v-btn-toggle>
      </div>
      <div class="d-flex align-baseline pt-1">
        <div
          class="text-capitalize subtitle-2 black--text medium bold mr-2 px-4 py-1"
        >
          Name
        </div>

        <v-btn
          text
          class="text-capitalize subtitle-2 black--text medium bold"
          active-class="light"
          @click="handleSort()"
        >
          Start time
          <v-icon v-if="sortOrder === 'asc'">
            arrow_drop_up
          </v-icon>
          <v-icon v-else>
            arrow_drop_down
          </v-icon>
        </v-btn>
      </div>
    </v-subheader>

    <v-card-text v-if="noChartMessage">
      {{ noChartMessage }}
    </v-card-text>
    <v-card-text v-else class="pt-0">
      <div>
        <apexchart
          class="mt-10"
          :height="`${75 * flowRun.task_runs.length + 75}px`"
          :options="chartData.options"
          :series="chartData.series"
          type="rangeBar"
        />

        <FullPagination
          :count-options="[10, 25, 50, 100]"
          :page="page"
          :total-items="flowRun.task_runs_aggregate.aggregate.count"
          @change-count-option="handleChangePagination"
          @change-page="newPage => (page = newPage)"
        />
      </div>
    </v-card-text>
  </v-card>

  <v-card v-else class="fill-height" fluid justify-center>
    <div />
  </v-card>
</template>

<style lang="scss" scoped>
p {
  font-family: sans-serif;
  margin-bottom: 21px;
  padding-left: 12px;
  padding-right: 40px;
}
</style>

<style lang="scss">
.task-run-search {
  margin: auto !important;
  margin-right: 0 !important;
}
</style>
