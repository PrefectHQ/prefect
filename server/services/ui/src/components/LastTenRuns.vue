<script>
import { mapMutations } from 'vuex'

export default {
  props: {
    flowRuns: {
      required: true,
      type: Array,
      // expecting a flow with 10 flow runs & for flow runs to have id & state & start time
      validator: flowRuns => {
        return (
          flowRuns[0].id &&
          'start_time' in flowRuns[0] &&
          'duration' in flowRuns[0] &&
          flowRuns[0].name &&
          flowRuns[0].state
        )
      }
    }
  },
  computed: {
    flowRunsReversed() {
      const flowRuns = this.flowRuns.slice()
      return flowRuns.reverse()
    }
  },
  methods: {
    ...mapMutations('sideDrawer', ['openDrawer'])
  }
}
</script>

<template>
  <v-layout justify-end align-center>
    <v-tooltip
      v-for="(flowRun, index) in flowRunsReversed"
      :key="index"
      xs1
      top
    >
      <template v-slot:activator="{ on }">
        <v-btn
          class="ma-0 pa-0"
          icon
          small
          @click="
            openDrawer({
              type: 'SideDrawerFlowRun',
              title: 'Flow Run Details',
              props: {
                flowRunId: flowRun.id
              }
            })
          "
        >
          <v-icon small :color="flowRun.state" v-on="on">
            brightness_1
          </v-icon>
        </v-btn>
      </template>
      <template v-slot:default>
        <div>Flow Run Name: {{ flowRun.name }}</div>
        <div>State: {{ flowRun.state }}</div>
        <div> Start Time: {{ flowRun.start_time | displayDateTime }}</div>
        <div> Duration: {{ flowRun.duration | duration }} </div>
      </template>
    </v-tooltip>
  </v-layout>
</template>
