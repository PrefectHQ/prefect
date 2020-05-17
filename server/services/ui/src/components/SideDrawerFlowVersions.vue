<script>
export default {
  components: {},
  props: {
    genericInput: {
      type: Object,
      required: true,
      validator: genericInput => genericInput.flowId
    }
  },
  data() {
    return {
      flowVersions: null,
      page: 1
    }
  },
  computed: {},
  apollo: {
    flowVersions: {
      query() {
        return require('@/graphql/Drawers/flow-versions-drawer.gql')
      },
      variables() {
        return {
          ...this.genericInput
        }
      },
      skip() {
        return !this.genericInput
      },
      pollInterval: 1000,
      update: data => data.flow
    }
  }
}
</script>

<template>
  <v-container class="side-drawer-flow-runs mb-10 pb-10">
    <v-layout v-if="flowVersions && flowVersions.error">
      Something Went Wrong
    </v-layout>

    <v-layout
      v-else-if="(flowVersions && flowVersions.loading) || !flowVersions"
      align-center
      justify-center
    >
      <v-progress-circular indeterminate color="primary" />
    </v-layout>

    <v-layout v-else column>
      <v-flex>
        <v-expansion-panels
          v-if="flowVersions && flowVersions.length"
          class="my-0"
          focusable
        >
          <v-expansion-panel
            v-for="flow in flowVersions[0].versions"
            :key="flow.id"
          >
            <v-expansion-panel-header>
              <v-layout column>
                <v-flex class="text-truncate">
                  <v-icon v-if="!flow.archived" dark color="green">
                    unarchive
                  </v-icon>
                  <v-icon v-else dark color="accent-pink">
                    archive
                  </v-icon>

                  Version {{ flow.version }}
                </v-flex>
              </v-layout>
            </v-expansion-panel-header>
            <v-expansion-panel-content class="px-n4 mx-n4">
              <v-layout class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Flow Name
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  <routerLink
                    class="link"
                    :to="{
                      name: 'flow',
                      params: { id: flow.id }
                    }"
                  >
                    {{ flow.name }}
                  </routerLink>
                </v-flex>
              </v-layout>
              <v-layout class="my-1" align-center wrap>
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Last Run State
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  <v-icon
                    v-if="flow.flow_runs.length"
                    class="pr-1"
                    :color="flow.flow_runs[0].state"
                    small
                  >
                    brightness_1
                  </v-icon>
                  <router-link
                    v-if="flow.flow_runs.length"
                    class="body-1 link"
                    :to="{
                      name: 'flow-run',
                      params: { id: flow.flow_runs[0].id }
                    }"
                  >
                    {{
                      flow.flow_runs.length
                        ? flow.flow_runs[0].state
                        : 'No Runs'
                    }}
                  </router-link>
                  <v-flex v-else>
                    No Runs
                  </v-flex>
                </v-flex>
              </v-layout>
              <v-layout class="my-2">
                <v-flex xs6 class="text-left body-1 font-weight-medium">
                  Created On
                </v-flex>
                <v-flex xs6 class="text-right body-1">
                  {{ flow.created | displayDateTime }}
                </v-flex>
              </v-layout>
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
        <v-flex v-else>
          Something went wrong.
        </v-flex>
      </v-flex>
      <v-flex xs10 offset-xs-1>
        <v-layout align-content-center justify-center>
          <v-pagination
            v-model="page"
            :length="1"
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
