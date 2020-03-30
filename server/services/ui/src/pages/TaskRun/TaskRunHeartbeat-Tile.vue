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
    taskRunId: {
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
    return {
      loading: 0,
      limit: 10
    }
  },
  computed: {
    heartbeat() {
      if (this.taskRun) {
        return this.taskRun[0].states
      }
      return []
    },
    count() {
      return this.taskRun
        ? this.taskRun[0].states_aggregate.aggregate.count
        : null
    }
  },
  apollo: {
    taskRun: {
      query: require('@/graphql/TaskRun/heartbeat.gql'),
      update: d => d.task_run,
      loadingKey: 'loading',
      pollInterval: 5000,
      variables() {
        return {
          taskRunId: this.taskRunId,
          timestamp: this.timestamp,
          state: this.checkedState,
          limit: this.limit
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

    <v-container class="pa-0 pr-4">
      <HeartbeatTimeline
        :loading="loading"
        :items="heartbeat"
        type="task_run_state"
      />
    </v-container>

    <v-divider></v-divider>

    <v-card-actions class="justify-center">
      <v-btn
        v-if="count > limit"
        class="blue--text"
        text
        outlined
        @click="limit += 5"
      >
        Show More
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<style lang="scss" scoped>
.state-interval-picker {
  font-size: 0.85rem;
  margin: auto;
  margin-right: 0;
  max-width: 150px;
}
</style>
