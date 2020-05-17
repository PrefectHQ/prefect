<script>
/* eslint-disable vue/no-v-html */

import moment from 'moment-timezone'
import vueScrollTo from 'vue-scrollto'

import store from '@/store'
import { STATE_TYPES } from '@/utils/states'

import DownloadMenu from './DownloadMenu'
import FilterMenu from './FilterMenu'
import LogRow from './LogRow'

const DEFAULT_LIMIT = 100
const LOG_LEVELS = ['CRITICAL', 'DEBUG', 'ERROR', 'INFO', 'WARNING']
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export default {
  components: {
    DownloadMenu,
    FilterMenu,
    LogRow
  },
  props: {
    // Set whether the logs are for a flow or a task
    entity: {
      default: 'flow',
      required: false,
      type: String,
      validator: value => ['flow', 'task'].includes(value)
    },
    // The GraphQL query that will be used to fetch the logs
    // Use the schema at "src/graphql/Logs/flow-run-logs.gql" as a reference
    query: {
      required: true,
      type: Object
    },
    // A special GraphQL query that's used to fetch the logs *around* a given log
    // Use the schema at "src/graphql/Logs/flow-run-logs-scoping.gql" as a reference
    queryForScoping: {
      required: false,
      type: Object,
      default: null
    },
    // The key that should be access in GraphQL data results to extract logs
    queryKey: {
      required: false,
      type: String,
      default: 'flow_run_by_pk'
    },
    // Determine whether or not to show filter descriptions at the top of the logs card
    showFilterDescription: {
      default: true,
      required: false,
      type: Boolean
    },
    // Any variables that should be passed into the logs GraphQL query
    variables: {
      required: true,
      type: Object
    }
  },
  data() {
    return {
      // Stored GraphQL query results
      // Logs to render on the page
      logsQueryResults: null,
      // Older & newer logs used for pagiation purposes
      logsQueryResultsOlder: null,
      logsQueryResultsNewer: null,
      // Information about a specific log whose ID is provided via the logId query param
      logsQueryResultsTarget: null,
      // Specialized query to get a certain amount of logs *around* a target log
      logsQueryResultsScoping: null,

      // GraphQL query variables
      // Any updates to these values will automatically update logsQueryResults, logsQueryResultsOlder, and logsQueryResultsNewer
      limit: DEFAULT_LIMIT,
      logLevelFilter: LOG_LEVELS,
      offset: 0,
      searchText: '',
      timestampFrom: null,
      timestampTo: null,

      // All possible log levels
      logLevels: LOG_LEVELS,

      // Filtering
      filterMenuOpen: false,

      // Show loader when logs are being fetched
      loadingOnStart: true,

      // User-set value that determines whether or not logs should be tailed during a run
      isTailingLogs: true,

      // Initiate scroll to a specific log, provided that a log ID is provided as a query param
      scrolledToQueryLog: false
    }
  },
  computed: {
    // Derive the state of the flow or task
    entityState() {
      if (!this.logsQueryResults) return 'Fetching logs'
      return this.logsQueryResults.state
    },
    // Derive whether or not the flow/task is in a non-finished state
    entityIsRunning() {
      return (
        this.entityState === 'Fetching logs' ||
        STATE_TYPES[this.entityState] !== 'Finished'
      )
    },
    // Determine whether user has filtered logs
    isFiltered() {
      return (
        this.searchText ||
        this.timestampFrom ||
        this.timestampTo ||
        this.logLevelFilter.length < this.logLevels.length
      )
    },
    // The number of logs rendered on the page
    logCount() {
      if (!this.logsQueryResults) return

      return this.logsQueryResults.logs.length
    },
    // Derive the list of logs from the GraphQL query
    logs() {
      if (!this.logsQueryResults) return

      return this.logsQueryResults.logs
        .slice()
        .reverse()
        .map(log => ({
          ...log,
          date: this.logDate(log.timestamp),
          time: this.logTime(log.timestamp),
          timestamp: moment(log.timestamp).format()
        }))
    },
    // Filter description text that tells the user what filters are currently applied to their logs
    // Example: "Showing 3 logs for all log levels from the beginning of time to now."
    logsFilterDescription() {
      let logLevelsMessage

      if (this.logLevelFilter.length === 5) {
        logLevelsMessage = 'for <b>all log levels</b>'
      } else if (this.logLevelFilter.length === 0) {
        logLevelsMessage = 'for <b>no log levels</b>'
      } else {
        logLevelsMessage = `for <b>log levels ${this.sententifyLogLevels()}</b>`
      }

      const searchText = this.searchText
        ? ` with text <b>"${this.searchText}"</b>`
        : ''

      const timestampFrom = this.timestampFrom
        ? `${this.logDate(this.timestampFrom)} ${this.logTime(
            this.timestampFrom
          )}`
        : 'the beginning of time'

      const timestampTo = this.timestampTo
        ? `${this.logDate(this.timestampTo)} ${this.logTime(this.timestampTo)}`
        : 'now'

      return `
        Showing logs ${searchText} ${logLevelsMessage}
        from <b>${timestampFrom}</b> to <b>${timestampTo}</b>.
      `
    }
  },
  watch: {
    logsQueryResults() {
      if (!this.logsQueryResults) return

      // Set the loading state to false once Apollo fetches log data
      this.loadingOnStart = false

      if (this.scrolledToQueryLog || !this.logsQueryResultsTarget) return

      this.scopeLogs()
    },
    logsQueryResultsTarget() {
      if (!this.logsQueryResultsTarget || !this.logsQueryResults) return

      this.scopeLogs()
    }
  },
  created() {
    this.$apollo.addSmartQuery('logsQueryResults', {
      query: this.query,
      variables() {
        return {
          ...this.variables,
          limit: this.limit,
          offset: this.offset,
          levels: this.logLevelFilter,
          searchText: this.searchText ? `%${this.searchText}%` : null,
          timestampFrom: this.timestampFrom,
          timestampTo: this.timestampTo
        }
      },
      pollInterval: 5000,
      update: data => data[this.queryKey]
    })

    this.$apollo.addSmartQuery('logsQueryResultsOlder', {
      query: this.query,
      variables() {
        return {
          ...this.variables,
          limit: this.limit,
          offset: this.offset + this.limit,
          levels: this.logLevelFilter,
          searchText: this.searchText ? `%${this.searchText}%` : null,
          timestampFrom: this.timestampFrom,
          timestampTo: this.timestampTo
        }
      },
      pollInterval: 5000,
      update: data => data[this.queryKey]
    })

    this.$apollo.addSmartQuery('logsQueryResultsNewer', {
      query: this.query,
      variables() {
        return {
          ...this.variables,
          limit: this.limit,
          offset:
            this.offset - this.limit < 0
              ? this.offset
              : this.offset - this.limit,
          levels: this.logLevelFilter,
          searchText: this.searchText ? `%${this.searchText}%` : null,
          timestampFrom: this.timestampFrom,
          timestampTo: this.timestampTo
        }
      },
      pollInterval: 5000,
      update: data => data[this.queryKey]
    })

    if (!this.$route.query.logId) return
    if (!UUID_REGEX.test(this.$route.query.logId)) return

    this.$apollo.addSmartQuery('logsQueryResultsTarget', {
      query: this.query,
      variables() {
        return {
          ...this.variables,
          logId: this.$route.query.logId
        }
      },
      update: data => data[this.queryKey]
    })
  },
  updated() {
    // Tail logs
    if (this.entityIsRunning && this.isTailingLogs) {
      this.scrollToEnd()
    }
  },
  methods: {
    // Remove the logId query param
    clearLogIdQuery() {
      this.$router.replace({
        query: { logId: undefined }
      })
    },
    // Apply any filters that the user sets
    handleFilter(filterResult) {
      this.limit = DEFAULT_LIMIT
      this.offset = 0
      this.searchText = filterResult.searchInput
      this.logLevelFilter = filterResult.logLevelFilterInput
      this.timestampFrom = filterResult.startDateTime
      this.timestampTo = filterResult.endDateTime

      this.filterMenuOpen = false
    },
    handleQueryLogScroll() {
      if (!this.shouldScrollToLog()) return

      this.scrolledToQueryLog = true
      this.scrollToLog(this.$route.query.logId)
    },
    // Fetch a batch of newer logs
    // For pagaination
    loadNewerLogs() {
      if (this.offset - DEFAULT_LIMIT < 0) {
        this.limit = this.logCount - (this.logCount - this.offset)
        this.offset = 0
      } else {
        this.offset -= DEFAULT_LIMIT
      }
    },
    // Fetch a batch of older logs
    // For pagination
    loadOlderLogs() {
      this.offset += this.limit

      if (this.limit < DEFAULT_LIMIT) {
        this.limit = DEFAULT_LIMIT
      }
    },

    // Format the log entry's date based on the datetime timestamp
    logDate(datetime) {
      let dt = moment(datetime)

      if (store.getters['user/timezone']) {
        dt = dt.tz(store.getters['user/timezone'])
      }

      return dt.format('MMMM Do YYYY')
    },
    // Format a log entry's time based on the datetime timestamp
    logTime(datetime) {
      let dt = moment(datetime)

      if (store.getters['user/timezone']) {
        dt = dt.tz(store.getters['user/timezone'])
      }

      return dt.format('h:mm:ssa z')
    },
    // Reset GraphQL query variables to their defaults
    resetQueryVars() {
      this.limit = DEFAULT_LIMIT
      this.logLevelFilter = LOG_LEVELS
      this.offset = 0
      this.searchText = ''
      this.timestampFrom = null
      this.timestampTo = null

      // Initiate reset on FilterMenu child
      if (this.$refs.filterMenu) {
        this.$refs.filterMenu.resetFilter()
      }
    },
    // Scroll to the bottom of the logs, for tailing purposes
    scrollToEnd() {
      const scrollEndElement = document.getElementById('scroll-end')
      if (!scrollEndElement) return

      vueScrollTo.scrollTo(scrollEndElement, 750, {
        container: '.logs-list',
        easing: 'ease-in',
        force: false,
        offset: -90
      })
    },
    // Scroll to a specific log entry
    scrollToLog(logId) {
      const logElement = this.$refs[`log-${logId}`]
      if (!logElement) return

      vueScrollTo.scrollTo(logElement[0].$el, 750, {
        container: '.logs-list',
        easing: 'ease-in',
        force: false,
        offset: -90,
        onDone: function(el) {
          el.focus()
        }
      })
    },
    // Create a phrase from the currently-set log levels
    // e.g. CRITICAL, DEBUG, and INFO
    sententifyLogLevels() {
      const words = this.logLevelFilter.slice()

      if (words.length === 1) {
        return words[0]
      } else if (words.length === 2) {
        return `${words[0]} and ${words[1]}`
      } else {
        words[words.length - 1] = `and ${words[words.length - 1]}`
        return words.join(', ')
      }
    },
    // Determine whether or not to scroll to a specific log
    shouldScrollToLog() {
      // Scroll to a specific log if...
      return (
        // the scroll hasn't happened yet,
        !this.scrolledToQueryLog &&
        // and an ID for the target log was provided as a query parameter,
        this.$route.query.logId
      )
    },
    // Show the logs surrounding a log whose ID was provided via query param
    scopeLogs() {
      if (!this.queryForScoping) return
      if (this.logs.length < DEFAULT_LIMIT) return

      const logTime = moment(
        this.logsQueryResultsTarget.logs[0].timestamp
      ).format()

      this.$apollo.addSmartQuery('logsQueryResultsScoping', {
        query: this.queryForScoping,
        variables() {
          return {
            ...this.variables,
            limit: DEFAULT_LIMIT / 2,
            timestamp: logTime
          }
        },
        result(res) {
          if (res.errors || !this.$route.query.logId) return

          const logsAfter = res.data.flow_run_by_pk.logs_after
          const logsBefore = res.data.flow_run_by_pk.logs_before

          if (logsAfter && logsAfter.length > 0) {
            this.timestampTo = logsAfter[logsAfter.length - 1].timestamp
          }

          if (logsBefore && logsBefore.length > 0) {
            this.timestampFrom = logsBefore[logsBefore.length - 1].timestamp
          }
        },
        update: data => data[this.queryKey]
      })
    }
  }
}
</script>

<template>
  <div data-private>
    <v-card class="logs-card" flat tile>
      <v-system-bar :color="entityState" :height="5" absolute>
        <!-- We should include a state icon here when we've got those -->
        <!-- <v-icon>{{ flow.flow_runs[0].state }}</v-icon> -->
      </v-system-bar>

      <v-toolbar class="mb-0 logs-card-title" color="white" elevation="4">
        <div v-if="showFilterDescription" v-html="logsFilterDescription"> </div>

        <v-spacer></v-spacer>
        <v-toolbar-items>
          <span v-if="$route.query.logId" class="toolbar-text">
            <a href="#" @click.prevent="clearLogIdQuery">
              Clear log query
            </a>
          </span>
          <span v-if="isFiltered" class="toolbar-text ml-4">
            <a href="#" @click.prevent="resetQueryVars">
              Clear filters
            </a>
          </span>
          <span class="state-indicator ml-4">
            <span>
              <v-tooltip v-if="entityState" bottom>
                <template v-slot:activator="{ on }">
                  <v-icon
                    class="state-indicator-icon"
                    :class="{ 'fade-in-out': entityIsRunning }"
                    :color="entityState"
                    v-on="on"
                  >
                    brightness_1
                  </v-icon>
                </template>
                <span>
                  {{ entity.toUpperCase() }} RUN STATE:
                  {{ entityState.toUpperCase(0) }}</span
                >
              </v-tooltip>
            </span>
          </span>

          <DownloadMenu v-if="logs" :logs="logs"></DownloadMenu>

          <FilterMenu
            ref="filterMenu"
            :menu-open="filterMenuOpen"
            :log-levels="logLevels"
            @filter="handleFilter"
            @open="filterMenuOpen = true"
            @close="filterMenuOpen = false"
          ></FilterMenu>
        </v-toolbar-items>
      </v-toolbar>

      <v-card-text v-if="loadingOnStart" class="bg-white loading-logs-progress">
        <v-progress-circular
          indeterminate
          color="primary"
        ></v-progress-circular>
      </v-card-text>

      <v-card-text
        v-else-if="logs && logs.length > 0"
        class="logs-list px-0 pt-0 pb-3"
        tabindex="0"
      >
        <v-btn
          v-if="logsQueryResultsOlder && logsQueryResultsOlder.logs.length > 0"
          x-small
          text
          class="ma-0 pa-0 load-logs-pagination load-logs-border-bottom"
          @click="loadOlderLogs"
        >
          Load older logs
        </v-btn>
        <LogRow
          v-for="(log, index) in logs"
          :key="index"
          :ref="`log-${log.id}`"
          :index="index"
          :log="log"
          @query-log-rendered="handleQueryLogScroll"
        >
        </LogRow>
        <v-btn
          v-if="offset > 0"
          x-small
          text
          class="ma-0 pa-0 load-logs-pagination load-logs-border-top"
          @click="loadNewerLogs"
        >
          Load newer logs
        </v-btn>
        <div
          v-else-if="entityIsRunning"
          class="pa-3 running-indicator bg-white"
        >
          <v-progress-linear indeterminate color="primary"></v-progress-linear>
        </div>
        <div id="scroll-end"></div>
      </v-card-text>

      <v-card-text v-else-if="entityIsRunning" class="bg-white">
        <div class="mb-3"> {{ entityState }}... </div>
        <v-progress-linear indeterminate color="primary"></v-progress-linear>
      </v-card-text>

      <v-card-text v-else class="bg-white no-logs-found">
        {{ entityIsRunning ? `${entityState}...` : 'No logs found.' }}
        <span v-if="logCount === 0" class="ma-0">
          Try
          <a href="#" @click.prevent="filterMenuOpen = true">expanding</a>
          or
          <a href="#" @click.prevent="resetQueryVars">resetting</a> your search.
        </span>
      </v-card-text>

      <v-tooltip
        v-if="entityIsRunning && logs && logs.length > 0"
        left
        open-delay="400"
        transition="fade-transition"
      >
        <template v-slot:activator="{ on }">
          <v-btn
            :color="isTailingLogs ? 'primary' : 'secondaryGrayLight'"
            :class="{ 'white--text': isTailingLogs }"
            class="tail-logs-button"
            small
            @click="isTailingLogs = !isTailingLogs"
            v-on="on"
          >
            <v-icon class="mr-2">offline_bolt</v-icon>
            Live
          </v-btn>
        </template>
        <span>
          Show the most recent logs while the {{ entity }} is running.
        </span>
      </v-tooltip>

      <div
        v-if="!entityIsRunning && logs && logs.length > 0"
        class="pa-0 logs-footer"
      ></div>
    </v-card>
  </div>
</template>

<style lang="scss" scoped>
.bg-white {
  background-color: #fff;
}

.date-picker {
  box-shadow: none;
}

.fade-in-out {
  animation: fade-oscillate 0.8s infinite alternate;
}

.toolbar-text {
  color: #fff;
  font-size: 0.9em;

  @media only screen and (min-width: 960px) {
    line-height: 64px;
  }

  @media only screen and (max-width: 959px) {
    line-height: 54px;
  }
}

.load-logs-border-bottom {
  border-bottom: 1px solid #dedede;
}

.load-logs-border-top {
  border-top: 1px solid #dedede;
}

.load-logs-pagination {
  background-color: #fff;
  border-radius: 0;
  height: 100%;
  width: 100%;
}

.loading-logs-progress {
  display: flex;
  flex-flow: row wrap;
  justify-content: center;
}

.logs-card {
  background-color: transparent;
  overflow: scroll;
  position: relative;
}

.logs-card-title {
  position: relative;
  z-index: 1;
}

.logs-footer {
  background-image: linear-gradient(transparent, 60%, rgba(221, 221, 221));
  height: 12px !important;
  position: relative;
  top: -12px;
}

.logs-list {
  max-height: 62vh;
  overflow-y: scroll;
  position: relative;
}

.no-logs-found {
  font-family: 'Source Code Pro', monospace;
}

.running-indicator {
  font-family: 'Source Code Pro', monospace;
}

.state-indicator {
  font-size: 0.9em;

  @media only screen and (min-width: 960px) {
    line-height: 64px;
  }

  @media only screen and (max-width: 959px) {
    line-height: 54px;
  }
}

.state-indicator-icon {
  border: 1px solid #777;
  border-radius: 50%;
}

.tail-logs-button {
  bottom: 8px;
  position: absolute;
  right: 8px;
  z-index: 10;
}

@keyframes fade-oscillate {
  from {
    opacity: 0;
  }

  to {
    opacity: 100%;
  }
}
</style>
