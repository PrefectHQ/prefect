import '@babel/polyfill'
import fetch from 'node-fetch'
import {
  ApolloServer,
  makeRemoteExecutableSchema,
  mergeSchemas,
  introspectSchema,
  RenameTypes,
  transformSchema,
  FilterRootFields
} from 'apollo-server'
import { HttpLink } from 'apollo-link-http'
import { v4 as uuidv4 } from 'uuid'

const APOLLO_API_PORT = process.env.APOLLO_API_PORT || '4200'
const APOLLO_API_BIND_ADDRESS = process.env.APOLLO_API_BIND_ADDRESS || '0.0.0.0'

const HASURA_API_URL =
  process.env.HASURA_API_URL || 'http://localhost:3000/v1alpha1/graphql'

const PREFECT_API_URL =
  process.env.PREFECT_API_URL || 'http://localhost:4201/graphql/'

const PREFECT_API_HEALTH_URL =
  process.env.PREFECT_API_HEALTH_URL || 'http://localhost:4201/health'

const PREFECT_SERVER__TELEMETRY__ENABLED =
  process.env.PREFECT_SERVER__TELEMETRY__ENABLED || 'false'
// Convert from a TOML boolean to a JavaScript boolean
const TELEMETRY_ENABLED =
  PREFECT_SERVER__TELEMETRY__ENABLED == 'true' ? true : false
const TELEMETRY_ID = uuidv4()
// --------------------------------------------------------------------
// Server
const depthLimit = require('graphql-depth-limit')
class PrefectApolloServer extends ApolloServer {
  async createGraphQLServerOptions(req, res) {
    const options = await super.createGraphQLServerOptions(req, res)
    return {
      ...options,
      validationRules: [depthLimit(7)]
    }
  }
}

function log(...items) {
  console.log(new Date().toISOString(), ...items)
}

const hasuraHTTPLink = new HttpLink({
  uri: HASURA_API_URL,
  fetch
})

// base HTTP link
const prefectHTTPLink = new HttpLink({
  uri: PREFECT_API_URL,
  fetch
})

async function buildSchema() {
  log('Building schema...')
  // create remote Hasura schema with admin auth link for introspection and unified hasura link otherwise
  const hasuraSchema = await makeRemoteExecutableSchema({
    schema: await introspectSchema(hasuraHTTPLink),
    link: hasuraHTTPLink
  })

  // create remote Prefect schema with admin auth link introspection and user auth link otherwise
  const prefectSchema = await makeRemoteExecutableSchema({
    schema: await introspectSchema(prefectHTTPLink),
    link: prefectHTTPLink
  })

  // Filter the Hasura schema
  const transformedHasuraSchema = transformSchema(hasuraSchema, [
    // remove all hasura mutations
    new FilterRootFields(operation => !(operation === 'Mutation'))
  ])

  // merge schemas
  const schema = mergeSchemas({
    schemas: [transformedHasuraSchema, prefectSchema]
  })
  log('Building schema complete!')
  return schema
}

// ensure the GraphQL server is up and running
async function checkGraphQLHealth() {
  var response = null
  try {
    response = await fetch(PREFECT_API_HEALTH_URL)
    return true
  } catch (err) {
    log(`Error fetching GraphQL health: ${err}`)
    return false
  }
}

async function safelyBuildSchema() {
  const isSafe = await checkGraphQLHealth()
  if (!isSafe) {
    throw new Error('Could not safely build a schema!')
  }
  return await buildSchema()
}

async function runServer() {
  const server = new PrefectApolloServer({
    schema: await safelyBuildSchema(),
    debug: false,
    introspection: true,
    playground: false,
    onHealthCheck: () => {
      return new Promise(async (resolve, reject) => {
        try {
          const isSafe = await checkGraphQLHealth()
          if (isSafe) {
            resolve()
          } else {
            reject()
          }
        } catch (err) {
          log(`error during health check: ${err}`)
          reject()
        }
      })
    },
    formatError: error => {
      log(JSON.stringify(error))
      return error
    },
    formatResponse: response => {
      return response
    },
    // this function is called whenever a request is made to the server in order to populate
    // the graphql context
    context: ({ req, connection }) => {
      // if `req` is passed, this is an HTTP request and we load the auth header for context
      if (req) {
        // pass along x-prefect headers; all others are ignored
        var headers = {}
        for (var key of Object.keys(req.headers)) {
          if (key.toLowerCase().startsWith('x-prefect')) {
            headers[key] = req.headers[key]
          }
        }
        return headers
      }
    }
  })

  server
    .listen({
      host: APOLLO_API_BIND_ADDRESS,
      port: APOLLO_API_PORT,
      family: 'IPv4'
    })
    .then(({ url }) => {
      console.log(`Server ready at ${url} 🚀`)
    })
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function runServerForever() {
  try {
    await runServer()
    send_telemetry_event('startup')
    if (TELEMETRY_ENABLED) {
      setInterval(() => {
        send_telemetry_event('heartbeat')
      }, 600000) // send heartbeat every 10 minutes
    }
  } catch (e) {
    log(e, e.message, e.stack)
    log('\nTrying again in 3 seconds...\n')
    await sleep(3000)
    await runServerForever()
  }
}

async function send_telemetry_event(event) {
  if (TELEMETRY_ENABLED) {
    try {
      // TODO add timeout
      const body = JSON.stringify({
        source: 'prefect_server',
        type: event,
        payload: { id: TELEMETRY_ID }
      })
      log(`Sending telemetry to Prefect Technnologies, Inc: ${body}`)

      fetch('https://sens-o-matic.prefect.io/', {
        method: 'post',
        body,
        headers: {
          'Content-Type': 'application/json',
          'X-Prefect-Event': 'prefect_server-0.0.1'
        }
      })
    } catch (error) {
      log(`Error sending telemetry event: ${error.message}`)
    }
  }
}

runServerForever()
