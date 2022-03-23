import { IStateDetailsResponse } from '@/models/IStateDetailsResponse'
import { IStateResponse } from '@/models/IStateResponse'
import { IState } from '@/models/State'
import { IStateDetails } from '@/models/StateDetails'

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
