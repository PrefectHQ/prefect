<script>
import moment from '@/utils/moment'
import KeyValueTable from '@/components/KeyValueTable'

export default {
  components: { KeyValueTable },
  props: {
    genericInput: {
      required: true,
      type: Object,
      validator: input => {
        return !!input.flowId
      }
    }
  },
  data() {
    return {
      flow: null,
      moment
    }
  },
  apollo: {
    flow: {
      query: require('@/graphql/Flow/flow-drawer.gql'),
      variables() {
        return { id: this.genericInput.flowId }
      },
      pollInterval: 1000,
      update: data => data.flow_by_pk
    }
  }
}
</script>

<template>
  <v-container class="side-drawer-flow mb-10 pb-10">
    <v-layout
      v-if="$apollo.queries.flow.loading || !flow"
      align-center
      justify-center
    >
      <v-progress-circular indeterminate color="primary" />
    </v-layout>
    <v-layout v-else column>
      <v-flex xs12>
        <div class="title">
          <router-link
            class="link"
            :to="{ name: 'flow-run', params: { id: flow.id } }"
          >
            {{ flow.name }}
          </router-link>
        </div>
      </v-flex>
      <v-flex xs12 class="mt-4">
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Description
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ flow.description }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Created
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ flow.created | displayDate }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Version
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ flow.version }}
          </v-flex>
        </v-layout>
        <v-layout class="mb-10">
          <v-expansion-panels focusable>
            <v-expansion-panel>
              <v-expansion-panel-header>
                <div class="body-1">
                  Parameters
                </div>
              </v-expansion-panel-header>
              <v-expansion-panel-content class="px-n4 mx-n4">
                <div v-if="!flow.parameters.length">
                  This flow has no parameters
                </div>
                <div
                  v-for="(parameter, index) in flow.parameters"
                  v-else
                  :key="index"
                >
                  <div class="body-1 font-weight-medium">
                    {{ index + 1 }}
                  </div>
                  <KeyValueTable :json-blob="parameter" />
                </div>
              </v-expansion-panel-content>
            </v-expansion-panel>
            <v-expansion-panel>
              <v-expansion-panel-header>
                <div class="body-1">
                  Environment
                </div>
              </v-expansion-panel-header>
              <v-expansion-panel-content class="px-n4 mx-n4">
                <KeyValueTable :json-blob="flow.environment" />
              </v-expansion-panel-content>
            </v-expansion-panel>
            <v-expansion-panel>
              <v-expansion-panel-header>
                <div class="body-1">
                  Storage
                </div>
              </v-expansion-panel-header>
              <v-expansion-panel-content class="px-n4 mx-n4">
                <KeyValueTable :json-blob="flow.storage" />
              </v-expansion-panel-content>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-layout>
      </v-flex>
    </v-layout>
  </v-container>
</template>

<style lang="scss" scoped>
.side-drawer-flow {
  overflow-y: scroll;
}
</style>
