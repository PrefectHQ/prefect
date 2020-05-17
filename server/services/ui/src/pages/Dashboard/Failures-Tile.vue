<script>
import { mapMutations } from 'vuex'
import { oneAgo } from '@/utils/dateTime'
import CardTitle from '@/components/Card-Title'
import { formatTime } from '@/mixins/formatTime'

export default {
  components: {
    CardTitle
  },
  mixins: [formatTime],
  props: {
    fullHeight: {
      required: false,
      type: Boolean,
      default: () => false
    }
  },
  data() {
    return {
      failures: null,
      loading: 0
    }
  },
  computed: {
    displayFailures() {
      if (!this.failures) return null
      const sorted = this.sortFailures(this.failures)
      return sorted
    },
    failureCount() {
      if (this.failures?.length) {
        return this.failures.length
      }
      return 0
    }
  },
  methods: {
    ...mapMutations('sideDrawer', ['openDrawer']),
    failedRuns(failure) {
      if (failure?.failed_count?.aggregate) {
        return failure.failed_count.aggregate.count
      }
      return ''
    },
    totalRuns(failure) {
      if (failure?.runs_count?.aggregate) {
        return failure.runs_count.aggregate.count
      }
      return ''
    },
    sortFailures(failures) {
      return failures.sort((flowRunA, flowRunB) => {
        if (flowRunA?.failed_count && flowRunB?.failed_count) {
          const aFailurePercentage =
            flowRunA.failed_count.aggregate.count /
            flowRunA.runs_count.aggregate.count
          const bFailurePercentage =
            flowRunB.failed_count.aggregate.count /
            flowRunB.runs_count.aggregate.count

          if (aFailurePercentage > bFailurePercentage) {
            return -1
          } else if (aFailurePercentage < bFailurePercentage) {
            return 1
          }
          return 0
        }
        return 0
      })
    }
  },
  apollo: {
    failures: {
      query: require('@/graphql/Dashboard/flow-failures.gql'),
      variables() {
        return {
          heartbeat: oneAgo(this.selectedDateFilter)
        }
      },
      loadingKey: 'loading',
      pollInterval: 10000,
      update: data =>
        data && data.flow
          ? data.flow.filter(flow => flow.failed_count.aggregate.count > 0)
          : null
    }
  }
}
</script>

<template>
  <v-card
    class="py-2 position-relative"
    tile
    :style="{
      height: fullHeight ? '100%' : 'auto'
    }"
  >
    <v-system-bar
      :color="
        loading > 0 ? 'secondaryGray' : failureCount ? 'failRed' : 'Success'
      "
      :height="5"
      absolute
    >
      <!-- We should include a state icon here when we've got those -->
      <!-- <v-icon>{{ flow.flow_runs[0].state }}</v-icon> -->
    </v-system-bar>

    <CardTitle
      :title="`${failureCount} Failed Flows`"
      icon="timeline"
      :icon-color="loading > 0 ? 'grey' : failureCount ? 'failRed' : 'Success'"
      :loading="loading > 0"
    >
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
    <v-list dense class="card-content">
      <v-slide-y-reverse-transition v-if="loading > 0" leave-absolute group>
        <v-skeleton-loader key="skeleton" type="list-item-three-line">
        </v-skeleton-loader>
      </v-slide-y-reverse-transition>

      <v-slide-y-reverse-transition
        v-else-if="failureCount"
        leave-absolute
        group
      >
        <v-lazy
          v-for="failure in displayFailures"
          :key="failure.id"
          :options="{
            threshold: 0.75
          }"
          min-height="40px"
          transition="fade"
        >
          <v-list-item
            class="text-truncate"
            :to="{
              name: 'flow',
              params: { id: failure.id }
            }"
          >
            <v-list-item-content>
              <v-list-item-title class="subtitle-2">
                <router-link
                  class="link"
                  :to="{
                    name: 'flow',
                    params: { id: failure.id }
                  }"
                  >{{ failure.name }}</router-link
                >
              </v-list-item-title>

              <v-list-item-subtitle>
                {{ failedRuns(failure) | number }}
                /
                {{ totalRuns(failure) | number }}
                Runs failed
              </v-list-item-subtitle>
            </v-list-item-content>
            <v-list-item-avatar
              ><v-icon>arrow_right</v-icon></v-list-item-avatar
            >
          </v-list-item>
        </v-lazy>
      </v-slide-y-reverse-transition>
      <v-slide-y-transition v-else leave-absolute group>
        <v-list-item key="no-data" color="grey">
          <v-list-item-avatar class="mr-0">
            <v-icon class="green--text">check</v-icon>
          </v-list-item-avatar>
          <v-list-item-content class="my-0 py-0">
            <div
              class="subtitle-1 font-weight-light"
              style="line-height: 1.25rem;"
            >
              No reported failures in the last {{ selectedDateFilter }}...
              Everything looks good!
            </div>
          </v-list-item-content>
        </v-list-item>
      </v-slide-y-transition>
    </v-list>
    <div v-if="failures && failures.length > 3" class="pa-0 footer"> </div>
  </v-card>
</template>

<style lang="scss" scoped>
.time-interval-picker {
  font-size: 0.85rem;
  margin: auto;
  margin-right: 0;
  max-width: 150px;
}

.card-content {
  max-height: 254px;
  overflow-y: scroll;
}

.footer {
  background-image: linear-gradient(transparent, 60%, rgba(0, 0, 0, 0.1));
  bottom: 6px;
  height: 6px !important;
  pointer-events: none;
  position: absolute;
  width: 100%;
}
</style>
