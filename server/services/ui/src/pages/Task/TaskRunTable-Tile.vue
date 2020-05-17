<script>
import CardTitle from '@/components/Card-Title'
import moment from 'moment-timezone'
import { oneAgo } from '@/utils/dateTime'
import store from '@/store'
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
    },
    dateTime: function(dt) {
      if (!dt) {
        return '...'
      }
      if (store.getters['user/timezone']) {
        return moment(dt)
          .tz(store.getters['user/timezone'])
          .format('M/D hh:mm:ss')
      }
      return moment(dt).format('M/D hh:mm:ss')
    }
  },
  props: {
    taskId: {
      required: true,
      type: String
    }
  },
  data() {
    return {
      dateFilters: [
        { name: '1 Hour', value: 'hour' },
        { name: '24 Hours', value: 'day' },
        { name: '7 Days', value: 'week' },
        { name: '30 Days', value: 'month' }
      ],
      headers: [
        {
          text: 'Flow Run',
          value: 'flow_run',
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
      selectedDateFilter: 'day',
      sortBy: 'start_time',
      sortDesc: true,
      taskRunDurations: {},
      loading: false
    }
  },
  computed: {
    tableTitle() {
      if (this.task) {
        return `${this.task.name} Task Runs`
      }
      return 'Task Runs'
    },
    offset() {
      return this.itemsPerPage * (this.page - 1)
    },
    searchFormatted() {
      if (!this.searchTerm) return null
      return `%${this.searchTerm}%`
    }
  },
  methods: {},
  apollo: {
    task: {
      query: require('@/graphql/Task/table-task-runs.gql'),
      variables() {
        const orderBy = {}
        orderBy[`${this.sortBy}`] = this.sortDesc ? 'desc' : 'asc'
        return {
          taskId: this.taskId,
          heartbeat: oneAgo(this.selectedDateFilter),
          limit: this.itemsPerPage,
          offset: this.offset,
          orderBy
        }
      },
      loadingKey: 'loading',
      pollInterval: 1000,
      update: data => {
        return data.task_by_pk
      }
    },
    taskRunsCount: {
      query: require('@/graphql/Task/table-task-runs-count.gql'),
      variables() {
        return {
          taskId: this.taskId,
          heartbeat: oneAgo(this.selectedDateFilter)
        }
      },
      pollInterval: 1000,
      update: data =>
        data && data.task_run_aggregate
          ? data.task_run_aggregate.aggregate.count
          : null
    }
  }
}
</script>

<template>
  <v-card class="pa-2 mt-2" tile>
    <CardTitle :title="tableTitle" icon="done_all">
      <v-select
        slot="action"
        v-model="selectedDateFilter"
        class="time-interval-picker"
        :items="dateFilters"
        dense
        solo
        item-text="name"
        item-value="value"
        hide-details
        flat
      >
        <template v-slot:prepend-inner>
          <v-icon color="black" x-small>
            history
          </v-icon>
        </template>
      </v-select>
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
        :items="task ? task.task_runs : null || []"
        :items-per-page.sync="itemsPerPage"
        :loading="loading"
        must-sort
        :page.sync="page"
        :server-items-length="taskRunsCount"
        :sort-by.sync="sortBy"
        :sort-desc.sync="sortDesc"
        :class="{ 'fixed-table': this.$vuetify.breakpoint.smAndUp }"
        calculate-widths
      >
        <template v-slot:item.flow_run="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <router-link
                class="link"
                :to="{ name: 'task-run', params: { id: item.id } }"
              >
                <span v-on="on">{{ item.flow_run.name }}</span>
              </router-link>
            </template>
            <span
              >{{ item.flow_run.name }} - {{ task.name }}
              <span v-if="item.map_index > -1">
                (Mapped Child {{ item.map_index }})</span
              ></span
            >
          </v-tooltip>
        </template>

        <template v-slot:item.start_time="{ item }">
          <v-tooltip v-if="item.start_time" top>
            <template v-slot:activator="{ on }">
              <span v-on="on"> {{ item.start_time | displayTime }}</span>
            </template>
            <span> {{ item.start_time | displayTimeDayMonthYear }}</span>
          </v-tooltip>
          <span v-else>...</span>
        </template>

        <template v-slot:item.end_time="{ item }">
          <v-tooltip v-if="item.end_time" top>
            <template v-slot:activator="{ on }">
              <span v-on="on">{{ item.end_time | displayTime }}</span>
            </template>
            <span>{{ item.end_time | displayTimeDayMonthYear }}</span>
          </v-tooltip>
          <span v-else>...</span>
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
              <v-icon class="mr-1 pointer" small :color="item.state" v-on="on">
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
</style>

<style lang="scss" scoped>
.time-interval-picker {
  font-size: 0.85rem;
  margin: auto;
  margin-right: 0;
  max-width: 150px;
}
</style>
