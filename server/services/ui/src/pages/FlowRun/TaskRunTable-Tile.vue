<script>
import CardTitle from '@/components/Card-Title'
import moment from 'moment-timezone'
import DurationSpan from '@/components/DurationSpan'

export default {
  components: {
    CardTitle,
    DurationSpan
  },
  filters: {
    duration: function(v) {
      if (!v) return ''
      let d = moment.duration(v)._data,
        string = ''

      if (d.days) string += ` ${d.days}d`
      if (d.hours) string += ` ${d.hours}h`
      if (d.minutes) string += ` ${d.minutes}m`
      if (d.seconds) string += ` ${d.seconds}s`
      return string
    }
  },
  props: {
    flowRunId: {
      required: true,
      type: String
    }
  },
  data() {
    return {
      incParent: false,
      headers: [
        {
          text: 'Task',
          value: 'task.name',
          sortable: false,
          width: '20%'
        },
        {
          text: 'Start Time',
          value: 'start_time',
          align: 'start',
          width: '15%'
        },
        { text: 'End Time', value: 'end_time', align: 'start', width: '15%' },
        { text: 'Duration', value: 'duration', align: 'end', width: '17.5%' },
        { text: 'State', value: 'state', align: 'end', width: '12.5%' }
      ],
      itemsPerPage: 15,
      page: 1,
      searchTerm: null,
      sortBy: 'start_time',
      sortDesc: true,
      taskRunDurations: {}
    }
  },
  computed: {
    offset() {
      return this.itemsPerPage * (this.page - 1)
    },
    tableTitle() {
      if (this.flowRun) {
        return `${this.flowRun.name} Task Runs`
      } else {
        return 'Task Runs'
      }
    },
    searchFormatted() {
      if (!this.searchTerm) return null
      return `%${this.searchTerm}%`
    }
  },
  methods: {
    hasChild(name) {
      const same = this.flowRun.task_runs.filter(
        taskRun => taskRun.task.name === name
      )
      if (same.length > 1) {
        this.incParent = true
        return true
      }
    }
  },
  apollo: {
    flowRun: {
      query: require('@/graphql/FlowRun/table-task-runs.gql'),
      variables() {
        const orderBy = {}
        orderBy[`${this.sortBy}`] = this.sortDesc ? 'desc' : 'asc'
        return {
          flowRunId: this.flowRunId,
          limit: this.itemsPerPage,
          name: this.searchFormatted,
          offset: this.offset,
          orderBy
        }
      },
      pollInterval: 1000,
      update: data => {
        return data && data.flow_run ? data.flow_run[0] : null
      }
    },
    taskRunsCount: {
      query: require('@/graphql/FlowRun/table-task-runs-count.gql'),
      variables() {
        return {
          flowRunId: this.flowRunId,
          name: this.searchFormatted
        }
      },
      pollInterval: 1000,
      update: data => {
        return data && data.task_run_aggregate
          ? data.task_run_aggregate.aggregate.count
          : null
      }
    }
  }
}
</script>

<template>
  <v-card class="pa-2" tile>
    <CardTitle :title="tableTitle" icon="done_all">
      <v-text-field
        slot="action"
        v-model="searchTerm"
        class="task-search"
        dense
        solo
        prepend-inner-icon="search"
        hide-details
        placeholder="Search by Task or Run Name"
      >
      </v-text-field>
    </CardTitle>

    <v-card-text>
      <v-data-table
        :footer-props="{
          showFirstLastPage: true,
          itemsPerPageOptions: [5, 15, 25, 50],
          firstIcon: 'first_page',
          lastIcon: 'last_page',
          prevIcon: 'keyboard_arrow_left',
          nextIcon: 'keyboard_arrow_right'
        }"
        :headers="headers"
        :header-props="{ 'sort-icon': 'arrow_drop_up' }"
        :items="flowRun ? flowRun.task_runs : [] || []"
        :items-per-page.sync="itemsPerPage"
        :loading="$apollo.queries.flowRun.loading"
        must-sort
        :page.sync="page"
        :server-items-length="taskRunsCount"
        :sort-by.sync="sortBy"
        :sort-desc.sync="sortDesc"
        :class="{ 'fixed-table': this.$vuetify.breakpoint.smAndUp }"
        calculate-widths
      >
        <template v-slot:item.task.name="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <router-link
                class="link"
                :data-cy="'task-run-table-link|' + item.task.name"
                :to="{ name: 'task-run', params: { id: item.id } }"
              >
                <span v-on="on"
                  >{{ item.task.name
                  }}<span v-if="item.map_index > -1">
                    (Mapped Child {{ item.map_index }})</span
                  ><span v-else-if="hasChild(item.task.name) || incParent">
                    (Parent)
                  </span>
                </span>
              </router-link>
            </template>
            <span>
              {{ flowRun.name }} - {{ item.task.name
              }}<span v-if="item.map_index > -1">
                (Mapped Child {{ item.map_index }})</span
              ><span v-else-if="hasChild(item.task.name)"> (Parent) </span>
            </span>
          </v-tooltip>
        </template>

        <template v-slot:item.start_time="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <span v-on="on"> {{ item.start_time | displayTime }}</span>
            </template>
            <span> {{ item.start_time | displayTimeDayMonthYear }}</span>
          </v-tooltip>
        </template>

        <template v-slot:item.end_time="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <span v-on="on">{{ item.end_time | displayTime }}</span>
            </template>
            <span>{{ item.end_time | displayTimeDayMonthYear }}</span>
          </v-tooltip>
        </template>

        <template v-slot:item.duration="{ item }">
          <span v-if="item.duration">{{ item.duration | duration }}</span>
          <DurationSpan
            v-else-if="item.start_time"
            :start-time="item.start_time"
          />
          <span v-else>...</span>
        </template>

        <template v-slot:item.state="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <v-icon
                class="mr-1 pointer"
                :data-cy="
                  'task-run-table-state|' +
                    item.task.name +
                    '|' +
                    item.state.toLowerCase()
                "
                small
                :color="item.state"
                v-on="on"
              >
                brightness_1
              </v-icon>
            </template>
            <span>{{ item.state }}</span>
          </v-tooltip>
        </template>
      </v-data-table>
    </v-card-text>
  </v-card>
</template>

<style lang="scss">
.fixed-table {
  table {
    table-layout: fixed;
  }
}

.v-data-table {
  font-size: 0.9rem !important;

  td {
    font-size: inherit !important;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.pointer {
  cursor: pointer;
}

.task-search {
  border-radius: 0 !important;
  font-size: 0.85rem;

  .v-icon {
    font-size: 20px !important;
  }
}
</style>
