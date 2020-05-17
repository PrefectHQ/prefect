<script>
import { mapMutations } from 'vuex'
import moment from '@/utils/moment'

export default {
  props: {
    items: {
      type: Array,
      required: false,
      default: () => []
    },
    loading: {
      type: Number,
      required: false,
      default: () => 0
    },
    type: {
      type: String,
      required: true
    }
  },
  methods: {
    ...mapMutations('sideDrawer', ['openDrawer']),
    formatTime(timestamp) {
      if (!timestamp) return ''

      let timeObj = moment(timestamp).tz(this.timezone),
        shortenedTz = moment()
          .tz(this.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone)
          .zoneAbbr()
      return `${
        timeObj ? timeObj.format('h:mma') : moment(timestamp).format('h:mma')
      } ${shortenedTz}`
    },
    formatDate(timestamp) {
      if (!timestamp) return ''

      let timeObj = moment(timestamp).tz(this.timezone)
      return `${
        timeObj
          ? timeObj.format('D MMMM YYYY')
          : moment(timestamp).format('D MMMM YYYY')
      }`
    },
    icon(item) {
      let icon

      switch (item.__typename) {
        case 'flow_run':
          icon = 'trending_up'
          break
        case 'task_run_state':
          icon = 'compare_arrows'
          break
        case 'task_run':
          icon = 'scatter_plot'
          break
      }
      return icon
    },
    routeTo(item) {
      if (this.type === 'task_run_state') {
        this.openDrawer({
          type: 'SideDrawerTaskRunState',
          title: 'Task Run State',
          props: {
            item: item
          }
        })
      } else {
        let routeName
        switch (this.type) {
          case 'flow':
          case 'flow_run':
            routeName = 'flow-run'
            break
          case 'task':
          case 'task_run':
            routeName = 'task-run'
            break
          default:
            routeName = null
            break
        }

        this.$router.push(
          routeName
            ? {
                name: routeName,
                params: { id: item.id }
              }
            : null
        )
      }
    },
    timelineItemTitle(item) {
      let name

      switch (this.type) {
        case 'flow':
          name = item.name
          break
        case 'flow_run':
          name = item.name
          break
        case 'task_run':
          name = item.task.name
          break
        case 'task_run_state':
          name = item.message
          break
        default:
          name = ''
          break
      }

      return name
    }
  }
}
</script>

<template>
  <v-timeline class="heartbeat-timeline" dense reverse>
    <v-slide-y-reverse-transition v-if="loading > 0" leave-absolute group>
      <v-timeline-item key="skeleton" small color="grey">
        <v-row class="align-center">
          <v-col cols="2">
            <v-skeleton-loader type="text"></v-skeleton-loader>
          </v-col>
          <v-col cols="7">
            <v-skeleton-loader type="text"></v-skeleton-loader>
            <v-skeleton-loader type="text"></v-skeleton-loader>
          </v-col>
          <v-col cols="3">
            <v-divider class="small-divider" />
          </v-col>
        </v-row>
      </v-timeline-item>
    </v-slide-y-reverse-transition>

    <v-slide-y-reverse-transition
      v-else-if="items.length > 0"
      leave-absolute
      group
    >
      <v-timeline-item
        v-for="item in items"
        :key="item.id"
        small
        :color="item.state"
        fill-dot
      >
        <v-list-item class="mx-0 pl-0" @click="routeTo(item)">
          <v-list-item-avatar class="ma-0">
            <v-icon left small>{{ icon(item) }}</v-icon>
          </v-list-item-avatar>
          <v-list-item-content class="my-0 py-0">
            <v-list-item-subtitle>
              {{ item.state }}
              <span class="caption">
                {{
                  item.state == 'Scheduled'
                    ? `for ${formatTime(item.scheduled_start_time)}`
                    : ''
                }}
              </span>
            </v-list-item-subtitle>
            <v-list-item-title>
              <v-tooltip bottom>
                <template v-slot:activator="{ on }">
                  <span v-on="on">
                    {{ timelineItemTitle(item) }}
                  </span>
                </template>
                <span>{{ timelineItemTitle(item) }}</span>
              </v-tooltip>
            </v-list-item-title>
            <v-list-item-subtitle v-if="type == 'flow'">
              <router-link :to="{ name: 'flow', params: { id: item.flow.id } }">
                {{ item.flow.name }}
              </router-link>
            </v-list-item-subtitle>
            <v-list-item-subtitle v-else class="caption">
              <v-tooltip bottom>
                <template v-slot:activator="{ on }">
                  <span class="caption" v-on="on">
                    {{
                      type == 'task_run_state'
                        ? item.result
                        : item.state_message
                    }}
                  </span>
                </template>
                <div>
                  {{
                    type == 'task_run_state' ? item.result : item.state_message
                  }}
                </div>
              </v-tooltip>
            </v-list-item-subtitle>
          </v-list-item-content>
          <v-list-item-avatar class="caption" style="min-width: 85px;">
            <v-tooltip top>
              <template v-slot:activator="{ on }">
                <span v-on="on">
                  {{ formatTime(item.state_timestamp || item.timestamp) }}
                </span>
              </template>
              <span>
                {{ formatDate(item.state_timestamp || item.timestamp) }}
              </span>
            </v-tooltip>
          </v-list-item-avatar>
          <v-divider class="small-divider" />
        </v-list-item>
      </v-timeline-item>
    </v-slide-y-reverse-transition>

    <v-slide-y-transition v-else leave-absolute group>
      <v-timeline-item key="no-data" color="grey">
        <v-list-item>
          <v-list-item-content class="my-0 py-0">
            <v-list-item-title>
              No recent activity
            </v-list-item-title>
          </v-list-item-content>
          <v-divider class="small-divider" />
        </v-list-item>
      </v-timeline-item>
    </v-slide-y-transition>
  </v-timeline>
</template>

<style lang="scss">
// stylelint-disable
.heartbeat-timeline {
  &::before {
    right: calc(23px - 1px) !important;
  }

  .small-divider {
    max-width: 15px;
  }

  .v-timeline-item__divider {
    min-width: 46px !important;
  }

  .v-timeline-item__body {
    max-width: calc(100% - 46px) !important;
  }
}
// stylelint-enable
</style>
