import { IState } from '../models/State'

export type IStateResponse = {
  id: string,
  type: string,
  message: string,
  state_details: Record<string, unknown>,
  data: Record<string, unknown>,
  timestamp: string,
  name: string,
}

export class StatesApi {

  public stateMapper(state: IStateResponse): IState {
    return {
      id: state.id,
      type: state.type,
      message: state.message,
      stateDetails: state.state_details,
      data: state.data,
      timestamp: state.timestamp,
      name: state.name,
    }
  }

}

export const States = new StatesApi()
