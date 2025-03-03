import { Meta, StoryObj } from '@storybook/react'
import { RunGraph } from './flow-run-graph'
import DemoData from './demo-data.json'
import DemoEvents from './demo-events.json'
import { isValid } from 'date-fns'
import { parseISO } from 'date-fns'
import { StateType } from '@prefecthq/graphs'

const meta = {
  component: RunGraph,
  title: 'Components/FlowRuns/FlowRunGraph',
} satisfies Meta<typeof RunGraph>

export default meta

type Story = StoryObj<typeof meta>

function reviver(key: string, value: any): any {
  if (typeof value === 'string') {
    const date = parseISO(value)
    if (isValid(date)) {
      return date
    }
  }

  if (key === 'nodes') {
    return new Map(value)
  }

  return value
}

function parseJson(json: unknown): any {
  return JSON.parse(JSON.stringify(json), reviver)
}

const stateTypeColors: Record<StateType, string> = {
  COMPLETED: '#219D4B',
  RUNNING: '#09439B',
  SCHEDULED: '#E08504',
  PENDING: '#554B58',
  FAILED: '#DE0529',
  CANCELLED: '#333333',
  CANCELLING: '#333333',
  CRASHED: '#EA580C',
  PAUSED: '#554B58',
}

export const Default: Story = {
  args: {
    config: {
      runId: 'foo',
      fetch: () => parseJson(DemoData),
      fetchEvents: () => parseJson(DemoEvents),
      styles: {
        node: (node) => ({
          background: stateTypeColors[node.state_type],
        }),
        state: (state) => ({
          background: stateTypeColors[state.type],
        }),
      },
    },
  },
}