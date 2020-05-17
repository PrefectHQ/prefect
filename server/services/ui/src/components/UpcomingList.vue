<script>
import moment from '@/utils/moment'

export default {
  props: {
    items: {
      required: false,
      type: Array,
      default: () => []
    },
    count: {
      required: false,
      type: Number,
      default: () => 0
    },
    loading: {
      required: false,
      type: Boolean,
      default: () => false
    }
  },
  methods: {
    formatTime(time) {
      let timeObj = moment(time).tz(this.timezone),
        shortenedTz = moment()
          .tz(this.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone)
          .zoneAbbr()
      return `${
        timeObj ? timeObj.format('hh:mm') : moment(time).format('hh:mm')
      } ${shortenedTz}`
    }
  }
}
</script>

<template>
  <v-list-group
    no-action
    dense
    class="upcoming-header"
    active-class="upcoming-active-class"
    :disabled="loading"
  >
    <template v-slot:prependIcon>
      <v-list-item-avatar class="ma-0 mx-2">
        <v-icon class="black--text">schedule</v-icon>
      </v-list-item-avatar>
    </template>

    <template v-slot:activator>
      <v-list-item-content class="mr-2">
        <v-list-item-title class="title">
          <span class="Scheduled--text font-weight-black mr-1">
            {{ count }}
          </span>
          Scheduled Flow Runs
        </v-list-item-title>
      </v-list-item-content>
    </template>

    <template v-slot:appendIcon>
      <v-list-item-avatar class="mr-2">
        <v-icon>arrow_drop_down</v-icon>
      </v-list-item-avatar>
    </template>

    <v-divider></v-divider>

    <v-list-item
      v-for="item in items"
      :key="item.id"
      dense
      three-line
      class="px-2 py-1"
      :to="{ name: 'flow-run', params: { id: item.id } }"
    >
      <v-list-item-avatar class="body-2 mx-2">
        <v-icon color="black">
          av_timer
        </v-icon>
      </v-list-item-avatar>
      <v-list-item-content>
        <v-list-item-title class="body-2">{{ item.name }}</v-list-item-title>
        <v-list-item-subtitle class="body-2 black--text">
          {{ formatTime(item.scheduled_start_time) }}
        </v-list-item-subtitle>
        <v-list-item-subtitle class="overline">
          {{ item.id }}
        </v-list-item-subtitle>
      </v-list-item-content>

      <v-list-item-avatar class="body-2">
        <v-icon class="grey--text">arrow_right</v-icon>
      </v-list-item-avatar>
    </v-list-item>

    <!-- We'll add this when we actually have a page for it -->
    <!-- <v-list-item
        dense
        class="px-2"
        :to="{ name: 'upcoming-flow-runs', params: { id: run.id } }"
      >
        <v-list-item-content>
          <v-list-item-title class="body-2">See all</v-list-item-title>
        </v-list-item-content>

        <v-list-item-avatar class="body-2">
          <v-icon class="grey--text">arrow_right</v-icon>
        </v-list-item-avatar>
      </v-list-item> -->
  </v-list-group>
</template>

<style lang="scss">
.upcoming-active-class:not(.v-list-item--disabled) {
  color: #000 !important;
}

// stylelint-disable
.upcoming-header {
  .v-list-item {
    padding: inherit !important;
  }
}

.v-list-group__header__prepend-icon {
  margin-right: inherit !important;
}
// stylelint-enable
</style>
