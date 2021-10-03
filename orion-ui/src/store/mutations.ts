import { GlobalFilter, RunState } from '@/typings/global'
import { State } from '.'

export const globalFilter = (state: State, g: GlobalFilter): void => {
  state.globalFilter = g
}

export const start = (state: State, d: Date): void => {
  state.globalFilter.start = d
}

export const end = (state: State, d: Date): void => {
  state.globalFilter.end = d
}

export const object = (state: State, object: string): void => {
  state.globalFilter.object = object
}

export const states = (state: State, states: RunState[]): void => {
  state.globalFilter.states = states
}
