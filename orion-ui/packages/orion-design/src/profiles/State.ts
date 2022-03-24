import { IStateResponse } from '@/models/IStateResponse'
import { IState } from '@/models/State'
import { Profile, translate } from '@/services/Translate'

export const stateProfile: Profile<IStateResponse, IState> = {
  toDestination(source) {
    return {
      id: source.id,
      type: source.type,
      message: source.message,
      stateDetails: source.state_details ? (this as typeof translate).toDestination('IStateDetailResponse:IStateDetails', source.state_details) : null,
      data: source.data,
      timestamp: source.timestamp,
      name: source.name,
    }
  },
  toSource(destination) {
    return {
      'id': destination.id,
      'type': destination.type,
      'message': destination.message,
      'state_details': destination.stateDetails ? (this as typeof translate).toSource('IStateDetailResponse:IStateDetails', destination.stateDetails) : null,
      'data': destination.data,
      'timestamp': destination.timestamp,
      'name': destination.name,
    }
  },
}