import '@babel/polyfill'
import fetch from 'node-fetch'
import { ApolloServer } from 'apollo-server-express'
import { v4 as uuidv4 } from 'uuid'
import { print, GraphQLError } from 'graphql'
import {
  introspectSchema,
  FilterRootFields,
  wrapSchema
} from '@graphql-tools/wrap'
import { stitchSchemas } from '@graphql-tools/stitch'

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
const express = require('express')
const depthLimit = require('graphql-depth-limit')
const app = express()

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

function makeExecutor(API_URL) {
  return async ({ document, variables, context }) => {
    // parse GQL document
    const query = print(document)

    // issue remote query
    const fetchResult = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ query, variables })
    })

    // get result
    const result = await fetchResult.json()

    // transform error keys into GraphQLErrors as a workaround for
    // https://github.com/ardatan/graphql-tools/pull/1572
    if (result.errors) {
      for (const error of result.errors) {
        Object.setPrototypeOf(error, GraphQLError.prototype)
      }
    }

    return result
  }
}

const hasuraExecutor = makeExecutor(HASURA_API_URL)
const prefectExecutor = makeExecutor(PREFECT_API_URL)

async function buildSchema() {
  log('Building schema...')
  // create remote Hasura schema with admin auth link for introspection and unified hasura link otherwise
  const hasuraSchema = wrapSchema({
    schema: await introspectSchema(hasuraExecutor),
    executor: hasuraExecutor,
    transforms: [
      // remove all hasura mutations
      new FilterRootFields((operation) => !(operation === 'Mutation'))
    ]
  })

  // create remote Prefect schema with admin auth link introspection and user auth link otherwise
  const prefectSchema = wrapSchema({
    schema: await introspectSchema(prefectExecutor),
    executor: prefectExecutor
  })

  // merge schemas
  const schema = stitchSchemas({
    subschemas: [{ schema: hasuraSchema }, { schema: prefectSchema }]
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
    formatError: (error) => {
      log(JSON.stringify(error))
      return error
    },
    formatResponse: (response) => {
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

  // without specifying a limit, we occasionally run into an implicit 100kb
  // limit set in bodyParser
  server.applyMiddleware({ app, path: '/', bodyParserConfig: { limit: '1pb' } })
  app.listen({
    host: APOLLO_API_BIND_ADDRESS,
    port: APOLLO_API_PORT,
    family: 'IPv4'
  })
  console.log(
    `Server ready at http://${APOLLO_API_BIND_ADDRESS}:${APOLLO_API_PORT} 🚀`
  )
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
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
      log(`Sending telemetry to Prefect Technologies, Inc.: ${body}`)

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
