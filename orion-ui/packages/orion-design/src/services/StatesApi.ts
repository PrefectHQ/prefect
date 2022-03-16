import { IFlowData } from '@/models/FlowData'
import { IState } from '@/models/State'
import { IStateDetails } from '@/models/StateDetails'
import { DateString } from '@/types/dates'

export type IStateDetailsResponse = {
  flow_run_id: string | null,
  task_run_id: string | null,
  child_flow_run_id: string | null,
  scheduled_time: DateString | null,
  cache_key: string | null,
  cache_expiration: string | null,
}

export type IStateResponse = {
  id: string,
  type: string,
  message: string,
  state_details: IStateDetails | null,
  data: IFlowData | null,
  timestamp: string,
  name: string,
}

export class StatesApi {

  public mapStateDetails(stateDetails: IStateDetailsResponse): IStateDetails {
    return {
      flowRunId: stateDetails.flow_run_id,
      taskRunId: stateDetails.task_run_id,
      childFlowRunId: stateDetails.child_flow_run_id,
      cacheKey: stateDetails.cache_key,
      scheduledTime: stateDetails.scheduled_time ? new Date(stateDetails.scheduled_time) : null,
      cacheExpiration: stateDetails.cache_expiration ? new Date(stateDetails.cache_expiration) : null,
    }
  }

  public mapStateResponse(state: IStateResponse): IState {
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

export const statesApi = new StatesApi()
