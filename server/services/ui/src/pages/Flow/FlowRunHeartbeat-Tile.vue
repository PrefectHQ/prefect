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
    flowId: {
      type: String,
      required: true
    }
  },
  data() {
    return { loading: 0 }
  },
  apollo: {
    heartbeat: {
      query: require('@/graphql/Flow/heartbeat.gql'),
      update: d => d.flow_run,
      loadingKey: 'loading',
      pollInterval: 5000,
      variables() {
        return {
          flowId: this.flowId,
          timestamp: this.timestamp,
          state: this.checkedState
        }
      }
    }
  }
}
</script>

<template>
  <v-card class="pa-2" tile>
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
        type="flow_run"
      />
    </v-container>

    <v-divider></v-divider>
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
