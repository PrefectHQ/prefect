import { GlobalFilter } from '@/typings/global'
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
