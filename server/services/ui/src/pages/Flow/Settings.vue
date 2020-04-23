<script>
import CardTitle from '@/components/Card-Title'

export default {
  components: { CardTitle },
  props: {
    flow: {
      required: true,
      type: Object
    }
  },
  data() {
    return {
      error: {
        heartbeat: null
      },
      loading: {
        heartbeat: false
      },
      selected: {
        heartbeatEnabled: this.flow.settings.heartbeat_enabled
      }
    }
  },
  computed: {
    isHeartbeatEnabled() {
      return this.flow.settings.heartbeat_enabled
    }
  },
  methods: {
    async _handleHeartbeatChange() {
      this.loading.heartbeat = true

      try {
        const updateHeartbeat = !this.selected.heartbeatEnabled
          ? await this.$apollo.mutate({
              mutation: require('@/graphql/Mutations/disable-flow-heartbeat.gql'),
              variables: {
                input: {
                  flowId: this.flow.id
                }
              },
              errorPolicy: 'all'
            })
          : await this.$apollo.mutate({
              mutation: require('@/graphql/Mutations/enable-flow-heartbeat.gql'),
              variables: {
                input: {
                  flowId: this.flow.id
                }
              },
              errorPolicy: 'all'
            })

        setTimeout(() => {
          let status = updateHeartbeat.data
            ? updateHeartbeat.data.enableFlowHeartbeat ||
              updateHeartbeat.data.disableFlowHeartbeat
            : false

          if (!status || !status.success) {
            this.error.heartbeat = status.errors[0].message
            this.loading.heartbeat = false
          } else {
            let heartbeatCheckInterval
            heartbeatCheckInterval = setInterval(() => {
              if (this.isHeartbeatEnabled == this.selected.heartbeatEnabled) {
                clearInterval(heartbeatCheckInterval)
                this.loading.heartbeat = false
              }
            }, 500)
          }
        }, 500)
      } catch (err) {
        this.loading.heartbeat = false
        this.error.heartbeat = err
        throw new Error(err)
      }
    }
  }
}
</script>

<template>
  <v-card class="pa-2 mt-2" tile>
    <CardTitle title="Flow Settings" icon="settings" />

    <v-card-text class="pl-12" style="max-width: 1000px;">
      <v-row class="mt-8">
        <v-col cols="12" class="pb-0">
          <div class="title primary--text">
            <!-- We don't really have the visual language necessary to use these I think -->
            <!-- <v-icon class="mr-3">favorite</v-icon> -->
            Heartbeat
          </div>
        </v-col>
        <v-col cols="12" class="pt-0">
          <v-tooltip bottom>
            <template v-slot:activator="{ on }">
              <div class="pb-1" style="display: inline-block;" v-on="on">
                <v-switch
                  v-model="selected.heartbeatEnabled"
                  hide-details
                  color="primary"
                  :loading="loading.heartbeat"
                  :disabled="loading.heartbeat"
                  @change="_handleHeartbeatChange"
                >
                  <template v-slot:label>
                    <label>
                      Heartbeat
                      <span
                        :class="
                          isHeartbeatEnabled
                            ? 'prefect--text'
                            : 'grey--text text--darken-2'
                        "
                        class="font-weight-medium"
                      >
                        {{ isHeartbeatEnabled ? 'Enabled' : 'Disabled' }}
                      </span>
                    </label>
                  </template>
                </v-switch>
              </div>
            </template>
            <span>
              {{ isHeartbeatEnabled ? 'Disable' : 'Enable' }} heartbeats for
              this flow.
            </span>
          </v-tooltip>

          <div class="mt-4">
            Heartbeats are sent by Prefect Core every 30 seconds and can be used
            to confirm the flow run and its associated task runs are healthy.
            See our
            <a
              href="https://docs.prefect.io/orchestration/concepts/services.html#zombie-killer"
              target="_blank"
            >
              Zombie Killer
            </a>
            <sup>
              <v-icon x-small color="primary">
                open_in_new
              </v-icon>
            </sup>
            documentation to learn about how this information is used to
            identify issues early in
            <a href="https://www.prefect.io/cloud" target="_blank"
              >Prefect Cloud
            </a>
            <sup>
              <v-icon x-small color="primary">
                open_in_new
              </v-icon> </sup
            >.
          </div>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<style lang="scss">
//
</style>
