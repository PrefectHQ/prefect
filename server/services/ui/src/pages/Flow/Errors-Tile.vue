<script>
import CardTitle from '@/components/Card-Title'
import { oneAgo } from '@/utils/dateTime'
import moment from '@/utils/moment'

export default {
  components: {
    CardTitle
  },
  props: {
    flowId: {
      required: true,
      type: String
    },
    fullHeight: {
      required: false,
      type: Boolean,
      default: () => false
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
      loading: 0,
      selectedDateFilter: 'day'
    }
  },
  methods: {
    formatTime(timestamp) {
      let timeObj = moment(timestamp).tz(this.timezone),
        shortenedTz = moment()
          .tz(this.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone)
          .zoneAbbr()
      return `${
        timeObj ? timeObj.format('h:mma') : moment(timestamp).format('h:mma')
      } ${shortenedTz}`
    },
    formatTimeRelative(timestamp) {
      let timeObj = moment(timestamp).tz(this.timezone)
      return timeObj ? timeObj.fromNow() : moment(timestamp).fromNow()
    }
  },
  apollo: {
    errors: {
      query: require('@/graphql/Flow/errors.gql'),
      variables() {
        return {
          flowId: this.flowId,
          heartbeat: oneAgo(this.selectedDateFilter)
        }
      },
      loadingKey: 'loading',
      pollInterval: 5000,
      update: data => data.flow_run
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
        loading > 0
          ? 'secondaryGray'
          : errors && errors.length > 0
          ? 'Failed'
          : 'Success'
      "
      :height="5"
      absolute
    >
      <!-- We should include a state icon here when we've got those -->
      <!-- <v-icon>{{ flow.flow_runs[0].state }}</v-icon> -->
    </v-system-bar>

    <CardTitle
      :title="`${errors ? errors.length : 0} Errors`"
      icon="error"
      :icon-color="
        loading > 0
          ? 'grey'
          : errors && errors.length > 0
          ? 'Failed'
          : 'Success'
      "
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

    <v-list dense class="error-card-content">
      <v-slide-y-reverse-transition v-if="loading > 0" leave-absolute group>
        <v-skeleton-loader key="skeleton" type="list-item-three-line">
        </v-skeleton-loader>
      </v-slide-y-reverse-transition>

      <v-slide-y-reverse-transition
        v-else-if="errors && errors.length > 0"
        leave-absolute
        group
      >
        <v-lazy
          v-for="error in errors"
          :key="error.id"
          :options="{
            threshold: 0.75
          }"
          min-height="40px"
          transition="fade"
        >
          <v-list-item
            :to="{
              name: 'flow-run',
              params: { id: error.id },
              query: {
                logId: error.logs.length > 0 ? error.logs[0].id : null
              }
            }"
          >
            <v-list-item-content>
              <v-list-item-subtitle class="font-weight-light">
                <span class="overline">
                  {{
                    error.logs.length
                      ? formatTimeRelative(error.logs[0].timestamp)
                      : ''
                  }}
                </span>
              </v-list-item-subtitle>
              <v-list-item-title
                class="subtitle-2 font-weight-light Failed--text text--darken-1"
              >
                {{
                  error.logs.length
                    ? error.logs[0].message
                    : 'No Log associated with this error.'
                }}
              </v-list-item-title>
              <v-list-item-subtitle class="font-weight-light">
                <router-link
                  :to="{ name: 'flow-run', params: { id: error.id } }"
                >
                  {{ error.name }}
                </router-link>
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
              No reported errors in the last {{ selectedDateFilter }}...
              Everything looks good!
            </div>
          </v-list-item-content>
        </v-list-item>
      </v-slide-y-transition>
    </v-list>

    <div v-if="errors && errors.length > 3" class="pa-0 error-footer"> </div>
  </v-card>
</template>

<style lang="scss" scoped>
.error-card-content {
  max-height: 254px;
  overflow-y: scroll;
}

.error-footer {
  background-image: linear-gradient(transparent, 60%, rgba(0, 0, 0, 0.1));
  bottom: 6px;
  height: 6px !important;
  pointer-events: none;
  position: absolute;
  width: 100%;
}

.time-interval-picker {
  font-size: 0.85rem;
  margin: auto;
  margin-right: 0;
  max-width: 150px;
}

.position-relative {
  position: relative;
}

a {
  text-decoration: none !important;
}
</style>
