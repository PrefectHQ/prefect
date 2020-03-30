<script>
import PrefectSchedule from '@/components/PrefectSchedule'
export default {
  components: { PrefectSchedule },
  props: {
    genericInput: {
      type: Object,
      required: true,
      validator: genericInput => genericInput.queryOptions
    }
  },
  data() {
    return {
      flowRuns: null,
      flowRunsCount: null,
      limit: 10,
      page: 1
    }
  },
  computed: {
    offset() {
      return this.limit * (this.page - 1)
    },
    totalPages() {
      if (!this.flowRunsCount) return 0
      return Math.ceil(this.flowRunsCount / this.limit)
    }
  },
  apollo: {
    flowRuns: {
      query() {
        if (this.genericInput.queryOptions.variables.state) {
          return require('@/graphql/Drawers/flow-runs-drawer-filter-state.gql')
        }
        return require('@/graphql/Drawers/flow-runs-drawer.gql')
      },
      variables() {
        return {
          ...this.genericInput.queryOptions.variables,
          limit: this.limit,
          offset: this.offset
        }
      },
      skip() {
        return !this.genericInput
      },
      pollInterval: 1000,
      update: data => data.flow_run
    },
    flowRunsCount: {
      query() {
        if (this.genericInput.queryOptions.variables.state) {
          return require('@/graphql/Drawers/flow-runs-drawer-count-filter-state.gql')
        }
        return require('@/graphql/Drawers/flow-runs-drawer-count.gql')
      },
      variables() {
        return {
          ...this.genericInput.queryOptions.variables
        }
      },
      skip() {
        return !this.genericInput
      },
      pollInterval: 1000,
      update: data => data.flow_run_aggregate.aggregate.count
    }
  }
}
</script>

<template>
  <v-container class="side-drawer-flow-runs mb-10 pb-10">
    <v-layout v-if="$apollo.queries.flowRuns && $apollo.queries.flowRuns.error">
      Something Went Wrong
    </v-layout>

    <v-layout
      v-else-if="
        ($apollo.queries.flowRuns && $apollo.queries.flowRuns.loading) ||
          !flowRuns
      "
      align-center
      justify-center
    >
      <v-progress-circular indeterminate color="primary" />
    </v-layout>

    <v-layout v-else column>
      <v-flex>
        <v-expansion-panels class="my-0" focusable>
          <v-expansion-panel v-for="flowRun in flowRuns" :key="flowRun.id">
            <v-expansion-panel-header>
              <v-layout column>
                <v-flex class="text-truncate">
                  {{ flowRun.flow.name }}
                </v-flex>
                <v-flex>
                  <v-layout align-center>
                    <div class="d-flex">
                      <v-icon small class="mr-1" :color="flowRun.state">
                        brightness_1
                      </v-icon>
                      <span class="caption">{{ flowRun.state }}</span>
                      <span class="caption mx-1">&#183;</span>
                      <span v-if="flowRun.end_time" class="caption">
                        {{ flowRun.end_time | displayDateTime }}
                      </span>
                      <span v-else class="caption">
                        {{ flowRun.scheduled_start_time | displayDateTime }}
                      </span>
                    </div>
                  </v-layout>
                </v-flex>
              </v-layout>
            </v-expansion-panel-header>
            <v-expansion-panel-content class="px-n4 mx-n4">
              <v-layout class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Flow Run Name
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  <router-link
                    class="body-1 link"
                    :to="{ name: 'flow-run', params: { id: flowRun.id } }"
                  >
                    {{ flowRun.name }}
                  </router-link>
                </v-flex>
              </v-layout>
              <v-layout v-if="flowRun.start_time" class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Start Time
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  {{ flowRun.start_time | displayDateTime }}
                </v-flex>
              </v-layout>
              <v-layout v-if="flowRun.duration" class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Duration
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  {{ flowRun.duration | duration }}
                </v-flex>
              </v-layout>
              <v-layout class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Scheduled Start
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  {{ flowRun.scheduled_start_time | displayDateTime }}
                </v-flex>
              </v-layout>
              <v-layout v-if="flowRun.flow.schedules.length" class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Schedule
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  <PrefectSchedule
                    :schedule="flowRun.flow.schedules[0].schedule"
                  />
                </v-flex>
              </v-layout>
              <v-layout class="body-2 text-uppercase" align-center>
                <RouterLink
                  class="link"
                  :to="{
                    name: 'flow-run-logs',
                    params: { id: flowRun.id }
                  }"
                >
                  Logs
                </RouterLink>
              </v-layout>
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-flex>
      <v-flex xs10 offset-xs-1>
        <v-layout align-content-center justify-center>
          <v-pagination
            v-model="page"
            :length="totalPages"
            max-buttons="5"
            next-icon="chevron_right"
            prev-icon="chevron_left"
          />
        </v-layout>
      </v-flex>
    </v-layout>
  </v-container>
</template>

<style lang="scss" scoped>
.side-drawer-flow-runs {
  overflow-y: scroll;
}
</style>
