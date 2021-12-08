import addSeconds from 'date-fns/addSeconds'
import isBefore from 'date-fns/isBefore'
import isWithinInterval from 'date-fns/isWithinInterval'
import { belongsTo, createServer, JSONAPISerializer, Model } from 'miragejs'
import FlowMock from './models/flowMock'
import FlowRunHistoryMock from './models/flowRunHistoryMock'
import FlowRunMock from './models/flowRunMock'
import FlowRunStateHistoryMock from './models/flowRunStateHistoryMock'
import { HistoryFilter } from './plugins/api'
import { StateNames } from './types/states'
import { server } from './utilities/api'
import { unique } from './utilities/arrays'
import { fakerRandomArray } from './utilities/faker'
import { snakeCase } from './utilities/strings'

export function startServer() {
  return createServer({
    environment: 'development',
    logging: false,
    timing: 0,
    models: {
      flow: Model,
      flowRun: Model.extend({
        flow: belongsTo()
      })
    },
    serializers: {
      application: JSONAPISerializer.extend({
        typeKeyForModel(model) {
          return snakeCase(model.modelName)
        },
        keyForAttribute(key) {
          return snakeCase(key)
        },
        keyForRelationship(key) {
          return snakeCase(key)
        }
      })
    },
    routes() {
      this.urlPrefix = server

      this.get('/flow_runs/:id', (schema, request) => {
        return schema.db.flowRuns.find(request.params.id)
      })

      this.post('/flow_runs/history', (schema, { requestBody }) => {
        const filter: HistoryFilter = JSON.parse(requestBody)
        const history: FlowRunHistoryMock[] = []
        const start = new Date(filter.history_start)
        const end = new Date(filter.history_end)

        let interval_start = new Date(start)
        let interval_end = addSeconds(
          interval_start,
          filter.history_interval_seconds
        )

        while (isBefore(interval_end, end)) {
          const runs: FlowRunMock[] = schema.db.flowRuns.where(
            (run: FlowRunMock) =>
              isWithinInterval(run.start_time, {
                start: interval_start,
                end: interval_end
              })
          )

          const states: FlowRunStateHistoryMock[] = []

          unique(runs.map((run) => run.state_type)).forEach((state_type) => {
            const stateRuns = runs.filter((run) => run.state_type == state_type)

            states.push(
              new FlowRunStateHistoryMock({
                state_name: StateNames.get(state_type),
                state_type: state_type,
                count_runs: stateRuns.length,
                sum_estimated_lateness: 0, // todo
                sum_estimated_run_time: 0 // todo
              })
            )
          })

          history.push(
            new FlowRunHistoryMock({
              interval_start,
              interval_end,
              states
            })
          )

          interval_start = interval_end
          interval_end = addSeconds(
            interval_start,
            filter.history_interval_seconds
          )
        }

        return history
      })

      this.post('/flows/filter', (schema, { requestBody }) => {
        const request = JSON.parse(requestBody)

        if (request.flow_runs?.id?.any_) {
          const flowRuns = schema.db.flowRuns.where((run: FlowRunMock) =>
            request.flow_runs.id.any_.includes(run.id)
          )
          const flowIds = flowRuns.map((run: FlowRunMock) => run.flow_id)

          return schema.db.flows.where((run: FlowRunMock) =>
            flowIds.includes(run.id)
          )
        }

        return schema.db.flows
      })

      this.post('/flows/count', (schema) => {
        return schema.db.flows.length
      })

      this.post('/flow_runs/count', (schema, { requestBody }) => {
        const request = JSON.parse(requestBody)
        const flows = request.flows?.id?.any_
        const stateTypes = request.flow_runs?.state?.type?.any_
        const stateNames = request.flow_runs?.state?.name?.any_

        if (flows) {
          return schema.db.flowRuns.where((run: FlowRunMock) => {
            return flows.includes(run.flow_id)
          }).length
        }

        if (stateTypes) {
          return schema.db.flowRuns.where((run: FlowRunMock) => {
            return stateTypes.includes(run.state.type)
          }).length
        }

        if (stateNames) {
          return schema.db.flowRuns.where((run: FlowRunMock) => {
            return stateNames.includes(run.state.name)
          }).length
        }

        return schema.db.flowRuns.length
      })

      this.post('/flow_runs/filter', (schema, { requestBody }) => {
        const request = JSON.parse(requestBody)
        const flows = request.flows?.id?.any_
        const stateTypes = request.flow_runs?.state?.type?.any_
        const stateNames = request.flow_runs?.state?.name?.any_

        if (flows) {
          return schema.db.flowRuns.where((run: FlowRunMock) => {
            return flows.includes(run.flow_id)
          })
        }

        if (stateTypes) {
          return schema.db.flowRuns.where((run: FlowRunMock) => {
            return stateTypes.includes(run.state.type)
          })
        }

        if (stateNames) {
          return schema.db.flowRuns.where((run: FlowRunMock) => {
            return stateNames.includes(run.state.name)
          })
        }

        return schema.db.flowRuns
      })
    },
    seeds(server) {
      fakerRandomArray({ min: 1, max: 10 }, () => {
        const flow = server.create('flow', { ...new FlowMock() })

        fakerRandomArray({ min: 1, max: 10 }, () => {
          server.create('flowRun', {
            ...new FlowRunMock({ flow_id: flow.id }),
            flow
          })
        })
      })
    }
  })
}
