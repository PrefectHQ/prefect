<script>
export default {
  name: 'SideDrawerFlowRun',
  props: {
    genericInput: {
      required: true,
      type: Object,
      validator: input => {
        return !!input.flowRunId
      }
    }
  },
  data() {
    return {
      flowRun: null
    }
  },
  computed: {
    createdBy() {
      if (this.flowRun.auto_scheduled) {
        return 'Prefect Scheduler'
      }
      return ''
    }
  },
  apollo: {
    flowRun: {
      query: require('@/graphql/Dashboard/flow-run-drawer.gql'),
      variables() {
        return { id: this.genericInput.flowRunId }
      },
      pollInterval: 1000,
      update: data => data.flow_run_by_pk
    }
  }
}
</script>

<template>
  <v-container class="side-drawer-flow mb-10 pb-10">
    <v-layout
      v-if="$apollo.queries.flowRun.loading || !flowRun"
      align-center
      justify-center
    >
      <v-progress-circular indeterminate color="primary" />
    </v-layout>
    <v-layout v-else column>
      <v-flex xs 12>
        <div class="title">
          <router-link
            class="link"
            :to="{ name: 'flow-run', params: { id: flowRun.id } }"
          >
            {{ flowRun.name }}
          </router-link>
        </div>
      </v-flex>
      <v-flex xs12 class="mt-4">
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Flow
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            <router-link
              class="link"
              :to="{
                name: 'flow',
                params: { id: flowRun.flow.id }
              }"
            >
              {{ flowRun.flow.name }}
            </router-link>
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Flow Version
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ flowRun.flow.version }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            State
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            <v-icon small :color="flowRun.state" class="mr-1">
              brightness_1
            </v-icon>
            <span>{{ flowRun.state }}</span>
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            State Message
          </v-flex>
          <v-flex
            xs6
            class="text-right body-1"
            style="word-break: break-all;
            word-break: break-word;"
          >
            {{ flowRun.state_message }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Scheduled Start Time
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ flowRun.scheduled_start_time | displayDateTime }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Start Time
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ flowRun.start_time | displayDateTime }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            End Time
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ flowRun.end_time | displayDateTime }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Duration
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ flowRun.duration | duration }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Parameters
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ flowRun.parameters }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Context
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ flowRun.context }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Created By
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ createdBy }}
          </v-flex>
        </v-layout>
      </v-flex>
      <v-flex class="my-3" xs12>
        <v-layout class="subtitle-1 text-uppercase" align-center>
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
      </v-flex>
    </v-layout>
  </v-container>
</template>

<style lang="scss" scoped>
.side-drawer-flow-runs {
  overflow-y: scroll;
}
</style>
