<script>
import CardTitle from '@/components/Card-Title'
const httpEndpoint = process.env.VUE_APP_GRAPHQL_HTTP

export default {
  components: {
    CardTitle
  },
  data() {
    return {
      graphqlUrl: httpEndpoint,
      connected: false,
      error: true,
      loading: 0,
      maxRetries: 10,
      retries: 0,
      skip: false,
      errorMessage: null
    }
  },
  computed: {
    cardColor() {
      if (this.connected) return 'Success'
      if (this.connecting) return 'grey'
      return 'Failed'
    },
    cardIcon() {
      if (this.connected) return 'signal_cellular_4_bar'
      if (this.connecting) return 'signal_cellular_connected_no_internet_4_bar'
      return 'signal_cellular_off'
    },
    connecting() {
      return this.error && this.retries <= this.maxRetries
    }
  },
  apollo: {
    hello: {
      query: require('@/graphql/Dashboard/hello.gql'),
      result(data) {
        if (data.loading) return

        this.connected = !data?.error && 'hello' in data.data
        this.error = data?.error

        if (this.error) {
          this.errorMessage = data.error
          if (this.retries <= this.maxRetries) {
            this.retries++
          } else {
            this.skip = true
            setTimeout(() => {
              this.retries = 0
              this.skip = false
            }, 10000)
          }
        } else {
          this.errorMessage = null
        }
      },
      loadingKey: 'loading',
      pollInterval: 1000,
      skip() {
        return this.skip
      },
      fetchPolicy: 'network-only',
      returnPartialData: true
    }
  }
}
</script>

<template>
  <v-card tile class="py-2 position-relative">
    <v-system-bar :height="5" absolute :color="cardColor" />
    <CardTitle :loading="loading > 0" :icon="cardIcon" :icon-color="cardColor">
      <v-row slot="title" no-gutters class="d-flex align-center justify-start">
        <div>API Status</div>
        <a
          v-if="!connected"
          class="ml-3"
          href="https://docs.prefect.io/core/concepts/configuration.html#environment-variables"
          target="_blank"
        >
          <v-tooltip top>
            <template v-slot:activator="{ on }">
              <v-icon color="grey darken-1" v-on="on">info</v-icon>
            </template>
            <span>
              <div>This is the most recent error:</div>
              <div class="my-4 font-italic font-weight-medium">
                {{ errorMessage }}
              </div>
              <div>
                Did you set the
                <span class="font-weight-bold">graphql_url</span> variable in
                <span class="font-weight-bold">~/.prefect/config.toml</span>
                correctly before starting Prefect Server?
              </div>
              <div>
                Click this icon to read more about configuring Prefect.
              </div>
            </span>
          </v-tooltip>
        </a>
      </v-row>
    </CardTitle>
    <v-list dense>
      <v-list-item>
        <v-list-item-avatar class="mr-0">
          <v-progress-circular
            v-if="connecting"
            indeterminate
            :size="15"
            :width="2"
            color="primary"
          />
          <v-icon v-else-if="error" class="Failed--text">
            priority_high
          </v-icon>
          <v-icon v-else class="Success--text">
            check
          </v-icon>
        </v-list-item-avatar>
        <v-list-item-content>
          <div
            class="subtitle-1 font-weight-light"
            style="line-height: 1.25rem;"
          >
            <span v-if="connected">Connected</span>
            <span v-else-if="connecting">Attempting to connect...</span>
            <span v-else>Couldn't connect</span>
          </div>
          <div class="font-weight-medium">
            {{ graphqlUrl }}
          </div>
        </v-list-item-content>
      </v-list-item>
    </v-list>
  </v-card>
</template>
