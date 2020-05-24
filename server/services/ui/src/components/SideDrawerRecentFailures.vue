<script>
export default {
  props: {
    genericInput: {
      type: Object,
      required: true,
      validator: genericInput => genericInput.queryOptions
    }
  },
  data() {
    return {
      failures: null,
      failuresCount: null,
      limit: 10,
      page: 1
    }
  },
  computed: {
    displayFailures() {
      if (!this.failures) return null

      return this.sortFailures(this.failures).slice(
        this.offset,
        this.limit + this.offset
      )
    },
    offset() {
      return this.limit * (this.page - 1)
    },
    totalPages() {
      if (!this.failuresCount) return 0
      return Math.ceil(this.failuresCount / this.limit)
    }
  },
  methods: {
    failurePercentage(failure) {
      return Math.round(
        (failure.flow.failed_runs_count.aggregate.count /
          failure.flow.runs_count.aggregate.count) *
          100
      )
    },
    sortFailures(failures) {
      return failures.sort((flowRunA, flowRunB) => {
        const aFailurePercentage =
          flowRunA.flow.failed_runs_count.aggregate.count /
          flowRunA.flow.runs_count.aggregate.count
        const bFailurePercentage =
          flowRunB.flow.failed_runs_count.aggregate.count /
          flowRunB.flow.runs_count.aggregate.count

        if (aFailurePercentage > bFailurePercentage) {
          return -1
        } else if (aFailurePercentage < bFailurePercentage) {
          return 1
        }
        return 0
      })
    }
  },
  apollo: {
    failures: {
      query: require('@/graphql/Dashboard/failures-drawer.gql'),
      variables() {
        return {
          ...this.genericInput.queryOptions.variables
        }
      },
      skip() {
        return !this.genericInput
      },
      update: data => data.flow_run
    },
    failuresCount: {
      query: require('@/graphql/Dashboard/failures-count.gql'),
      variables() {
        return {
          ...this.genericInput.queryOptions.variables
        }
      },
      skip() {
        return !this.genericInput
      },
      update: data => data.flow_aggregate.aggregate.count
    }
  }
}
</script>

<template>
  <v-container class="side-drawer-flow-runs mb-10 pb-10">
    <v-layout v-if="$apollo.queries.failures && $apollo.queries.failures.error">
      Something Went Wrong
    </v-layout>

    <v-layout
      v-else-if="
        ($apollo.queries.failures && $apollo.queries.failures.loading) ||
          !failures
      "
      align-center
      justify-center
    >
      <v-progress-circular indeterminate color="primary" />
    </v-layout>

    <v-layout v-else column>
      <v-flex>
        <v-expansion-panels class="my-0" focusable>
          <v-expansion-panel
            v-for="failure in displayFailures"
            :key="failure.id"
          >
            <v-expansion-panel-header>
              <v-layout column>
                <v-flex>
                  {{ failure.flow.name }}
                </v-flex>
                <v-flex>
                  <v-layout align-center>
                    <div>
                      {{
                        failure.flow.failed_runs_count.aggregate.count | number
                      }}
                      /
                      {{ failure.flow.runs_count.aggregate.count | number }}
                    </div>
                    <div class="ml-1 d-flex">
                      <v-icon small class="mr-1" color="Failed">
                        brightness_1
                      </v-icon>
                      <span>Failed</span>
                    </div>
                  </v-layout>
                </v-flex>
              </v-layout>
            </v-expansion-panel-header>

            <v-expansion-panel-content class="px-n4 mx-n4">
              <v-layout class="my-2">
                <v-flex xs6 class="text-left font-weight-medium">
                  Failure Percentage
                </v-flex>
                <v-flex xs6 class="text-right">
                  {{ failurePercentage(failure) }}%
                </v-flex>
              </v-layout>
              <div>Most Recent Failure</div>
              <v-layout class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Name
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  <RouterLink
                    class="link"
                    :to="{ name: 'flow-run', params: { id: failure.id } }"
                  >
                    {{ failure.name }}
                  </RouterLink>
                </v-flex>
              </v-layout>
              <v-layout class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Scheduled Start Time
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  <span>{{
                    failure.scheduled_start_time | displayDateTime
                  }}</span>
                </v-flex>
              </v-layout>
              <v-layout class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Start Time
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  <span>{{ failure.start_time | displayDateTime }}</span>
                </v-flex>
              </v-layout>
              <v-layout class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  End Time
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  <span>{{ failure.end_time | displayDateTime }}</span>
                </v-flex>
              </v-layout>
              <v-layout class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Duration
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  <span>{{ failure.duration | duration }}</span>
                </v-flex>
              </v-layout>
              <v-layout class="body-2 mx-2 text-uppercase" align-center>
                <RouterLink
                  class="link"
                  :to="{
                    name: 'flow-run-logs',
                    params: { id: failure.id }
                  }"
                >
                  Logs
                </RouterLink>
              </v-layout>
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-flex>

      <v-flex>
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
