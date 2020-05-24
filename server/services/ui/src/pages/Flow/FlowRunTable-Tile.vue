<script>
import CardTitle from '@/components/Card-Title'
import moment from 'moment-timezone'
import { oneAgo } from '@/utils/dateTime'
//Filters are pure functions so importing store rather than vuex. (https://github.com/vuejs/vuex/issues/1054)
import store from '@/store'

export default {
  components: { CardTitle },
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
    flowId: {
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
      selectedDateFilter: 'month',
      flowRuns: null,
      flowRunsCount: null,
      headers: [
        {
          text: 'Name',
          value: 'name',
          width: '20%'
        },
        {
          text: 'Scheduled Start',
          value: 'scheduled_start_time',
          align: 'start',
          width: '17.5%'
        },
        {
          text: 'Start Time',
          value: 'start_time',
          align: 'start',
          width: '17.5%'
        },
        { text: 'End Time', value: 'end_time', align: 'start', width: '17.5%' },
        { text: 'Duration', value: 'duration', align: 'end', width: '17.5%' },
        { text: 'State', value: 'state', align: 'end', width: '12.5%' }
      ],
      itemsPerPage: 15,
      page: 1,
      searchTerm: null,
      sortBy: 'scheduled_start_time',
      sortDesc: true
    }
  },
  computed: {
    offset() {
      return this.itemsPerPage * (this.page - 1)
    },
    searchFormatted() {
      if (!this.searchTerm) return null
      return `%${this.searchTerm}%`
    }
  },
  apollo: {
    flowRuns: {
      query: require('@/graphql/Flow/table-flow-runs.gql'),
      variables() {
        const orderBy = {}
        orderBy[`${this.sortBy}`] = this.sortDesc ? 'desc' : 'asc'

        return {
          flowId: this.flowId,
          heartbeat: oneAgo(this.selectedDateFilter),
          limit: this.itemsPerPage,
          name: this.searchFormatted,
          offset: this.offset,
          orderBy
        }
      },
      pollInterval: 3000,
      update: data => data.flow_run
    },
    flowRunsCount: {
      query: require('@/graphql/Flow/table-flow-runs-count.gql'),
      variables() {
        return {
          flowId: this.flowId,
          heartbeat: oneAgo(this.selectedDateFilter),
          name: this.searchFormatted
        }
      },
      pollInterval: 3000,
      update: data =>
        data && data.flow_run_aggregate
          ? data.flow_run_aggregate.aggregate.count
          : null
    }
  }
}
</script>

<template>
  <v-card class="pa-2 mt-2" tile>
    <CardTitle title="Flow Runs" icon="trending_up">
      <v-text-field
        slot="action"
        v-model="searchTerm"
        class="task-search"
        dense
        solo
        prepend-inner-icon="search"
        hide-details
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
        :items="flowRuns || []"
        :items-per-page.sync="itemsPerPage"
        :loading="$apollo.queries.flowRuns.loading"
        must-sort
        :page.sync="page"
        :server-items-length="flowRunsCount"
        :sort-by.sync="sortBy"
        :sort-desc.sync="sortDesc"
        :class="{ 'fixed-table': this.$vuetify.breakpoint.smAndUp }"
        calculate-widths
      >
        <template v-slot:item.name="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <router-link
                class="link"
                :to="{ name: 'flow-run', params: { id: item.id } }"
              >
                <span v-on="on">{{ item.name }}</span>
              </router-link>
            </template>
            <span>{{ item.name }}</span>
          </v-tooltip>
        </template>

        <template v-slot:item.scheduled_start_time="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <span v-on="on">{{ item.scheduled_start_time | dateTime }}</span>
            </template>
            <span>{{ item.scheduled_start_time | dateTime }}</span>
          </v-tooltip>
        </template>

        <template v-slot:item.start_time="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <span v-on="on"> {{ item.start_time | dateTime }}</span>
            </template>
            <span> {{ item.start_time | dateTime }}</span>
          </v-tooltip>
        </template>

        <template v-slot:item.end_time="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <span v-on="on">{{ item.end_time | dateTime }}</span>
            </template>
            <span>{{ item.end_time | dateTime }}</span>
          </v-tooltip>
        </template>

        <template v-slot:item.duration="{ item }">
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <span v-on="on">{{ item.duration | duration }}</span>
            </template>
            <span>{{ item.duration | duration }}</span>
          </v-tooltip>
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
