<script>
import CardTitle from '@/components/Card-Title'
import HeartbeatTimeline from '@/components/HeartbeatTimeline'
import { heartbeatMixin } from '@/mixins/heartbeatMixin.js'

export default {
  components: {
    CardTitle,
    HeartbeatTimeline
  },
  mixins: [heartbeatMixin],
  // These should eventually be moved here as data props
  // instead of as passed in props
  props: {
    taskId: {
      type: String,
      required: true
    },
    timestamp: {
      type: String,
      required: false,
      default: () => null
    }
  },
  data() {
    return { loading: 0 }
  },
  apollo: {
    heartbeat: {
      query: require('@/graphql/Task/heartbeat.gql'),
      update: d => d.task_run,
      loadingKey: 'loading',
      pollInterval: 5000,
      variables() {
        return {
          taskId: this.taskId,
          timestamp: this.timestamp,
          state: this.checkedState
        }
      }
    }
  }
}
</script>

<template>
  <v-card class="pa-2">
    <CardTitle title="Activity" icon="show_chart">
      <v-select
        slot="action"
        v-model="state"
        class="state-interval-picker font-weight-regular"
        :items="states"
        label="State"
        dense
        solo
        hide-details
        flat
      >
        <template v-slot:prepend-inner>
          <v-icon color="black" x-small>
            label_important
          </v-icon>
        </template>
      </v-select>
    </CardTitle>

    <v-container class="pa-0 pr-4 pl-6">
      <HeartbeatTimeline :loading="loading" :items="heartbeat" type="task" />
    </v-container>
  </v-card>
</template>
