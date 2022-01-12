import { State as StateType } from '@/types/states'

export interface IState {
  id: string
  type: StateType
  message: string
  state_details: { [key: string]: any }
  data: { [key: string]: any }
  timestamp: string
  name: string
}

export default class State implements IState {
  public id: string
  public type: StateType
  public message: string
  public state_details: { [key: string]: any }
  public data: { [key: string]: any }
  public timestamp: string
  public name: string

  constructor(state: IState) {
    this.id = state.id
    this.type = state.type
    this.message = state.message
    this.state_details = state.state_details
    this.data = state.data
    this.timestamp = state.timestamp
    this.name = state.name
  }
}
