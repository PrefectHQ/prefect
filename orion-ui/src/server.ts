import { snakeCase, RunHistory, FlowRun, StateHistory, mocker } from '@prefecthq/orion-design'
import { addSeconds, isBefore, isWithinInterval } from 'date-fns'
import { belongsTo, createServer, JSONAPISerializer, Model } from 'miragejs'
import { UiSettings } from './services/uiSettings'
import { unique } from './utilities/arrays'

export function startServer(): ReturnType<typeof createServer> {
  return createServer({
    environment: 'development',
    logging: false,
    timing: 0,
    models: {
      flow: Model,
      flowRun: Model.extend({
        flow: belongsTo(),
      }),
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
        },
      }),
    },
    async routes() {
      this.urlPrefix = await UiSettings.get('apiUrl')

      this.get('/flow_runs/:id', (schema, request) => {
        return schema.db.flowRuns.find(request.params.id)
      })

      this.post('/flow_runs/history', (schema, { requestBody }) => {
        const filter: any = JSON.parse(requestBody)
        const history: RunHistory[] = []
        const start = new Date(filter.history_start)
        const end = new Date(filter.history_end)

        let intervalStart = new Date(start)
        let intervalEnd = addSeconds(
          intervalStart,
          filter.history_interval_seconds,
        )

        while (isBefore(intervalEnd, end)) {
          const runs: FlowRun[] = schema.db.flowRuns.where(
            (run: FlowRun) => run.startTime && isWithinInterval(run.startTime, {
              start: intervalStart,
              end: intervalEnd,
            }),
          )

          const states: StateHistory[] = []

          unique(runs.map((run) => run.stateType)).forEach((stateType) => {
            const stateRuns = runs.filter((run) => run.stateType == stateType)
            const state = mocker.create('flowRunStateHistory', [{ stateType, stateRuns }])

            states.push(state)
          })

          history.push(mocker.create('flowRunHistory', [{ intervalStart, intervalEnd, states }]))

          intervalStart = intervalEnd
          intervalEnd = addSeconds(intervalStart, filter.history_interval_seconds)
        }

        return history
      })

      this.post('/flows/filter', (schema, { requestBody }) => {
        const request = JSON.parse(requestBody)

        if (request.flow_runs?.id?.any_) {
          const flowRuns = schema.db.flowRuns.where((run: FlowRun) => request.flow_runs.id.any_.includes(run.id),
          )
          const flowIds = flowRuns.map((run: FlowRun) => run.flowId)

          return schema.db.flows.where((run: FlowRun) => flowIds.includes(run.id),
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
          return schema.db.flowRuns.where((run: FlowRun) => {
            return flows.includes(run.flowId)
          }).length
        }

        if (stateTypes) {
          return schema.db.flowRuns.where((run: FlowRun) => {
            return stateTypes.includes(run.state?.type)
          }).length
        }

        if (stateNames) {
          return schema.db.flowRuns.where((run: FlowRun) => {
            return stateNames.includes(run.state?.name)
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
          return schema.db.flowRuns.where((run: FlowRun) => {
            return flows.includes(run.flowId)
          })
        }

        if (stateTypes) {
          return schema.db.flowRuns.where((run: FlowRun) => {
            return stateTypes.includes(run.state?.type)
          })
        }

        if (stateNames) {
          return schema.db.flowRuns.where((run: FlowRun) => {
            return stateNames.includes(run.state?.name)
          })
        }

        return schema.db.flowRuns
      })
    },
    seeds(server) {
      const numberOfFlows = mocker.create('number', [1, 10])

      new Array(numberOfFlows).fill(null).forEach(() => {
        const flow = server.create('flow', { ...mocker.create('flow') })
        const numberOfFlowRuns = mocker.create('number', [1, 10])

        new Array(numberOfFlowRuns).fill(null).forEach(() => {
          server.create('flowRun', {
            ...mocker.create('flowRun', [{ flowId: flow.id }]),
            flow,
          })
        })
      })
    },
  })
}
