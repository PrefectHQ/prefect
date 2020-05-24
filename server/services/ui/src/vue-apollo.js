import Vue from 'vue'
import VueApollo from 'vue-apollo'
import { createApolloClient } from 'vue-cli-plugin-apollo/graphql-client'

// Install the vue plugin
Vue.use(VueApollo)

// Http endpoint
const httpEndpoint = process.env.VUE_APP_GRAPHQL_HTTP

// Files URL root
export const filesRoot =
  process.env.VUE_APP_FILES_ROOT ||
  httpEndpoint.substr(0, httpEndpoint.indexOf('/graphql'))

Vue.prototype.$filesRoot = filesRoot

// FIXME This is a hack, we'll have a better way to do this when we implement subscriptions
function checkIfOnlineUntilWeAre() {
  if (!navigator.onLine) {
    setTimeout(checkIfOnlineUntilWeAre.bind(this), 3000)
  } else {
    this.$apollo.skipAll = false
  }
}

// Config
export const defaultOptions = {
  httpEndpoint,
  wsEndpoint: null,
  // Enable Automatic Query persisting with Apollo Engine
  persisting: false,
  // Use websockets for everything (no HTTP)
  // You need to pass a `wsEndpoint` for this to work
  websocketsOnly: false,
  ssr: false
}

// Create apollo client
export const createApolloProvider = () => {
  const { apolloClient, wsClient } = createApolloClient({
    ...defaultOptions
  })
  apolloClient.wsClient = wsClient

  // Create vue apollo provider
  const apolloProvider = new VueApollo({
    defaultClient: apolloClient,
    defaultOptions: {
      $query: {
        // fetchPolicy: 'cache-and-network',
        errorPolicy: 'all'
      },
      $subscription: {
        errorPolicy: 'all'
      }
    },
    async errorHandler(
      { graphQLErrors, networkError },
      vm,
      key,
      type,
      options
    ) {
      if (navigator && !navigator.onLine) {
        this.$apollo.skipAll = true
        setTimeout(checkIfOnlineUntilWeAre.bind(this), 3000)
      } else {
        /* eslint-disable no-console */
        console.log('graphQLErrors', graphQLErrors)
        console.log('networkError', networkError)
        console.log('vm', vm)
        console.log('key', key)
        console.log('type', type)
        console.log('options', options)
        /* eslint-enable no-console */
      }
    }
  })
  return apolloProvider
}
