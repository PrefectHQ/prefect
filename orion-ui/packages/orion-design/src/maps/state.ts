import { IStateResponse } from '@/models/IStateResponse'
import { IState } from '@/models/State'
import { MapFunction } from '@/services/Mapper'

export const mapIStateResponseToIState: MapFunction<IStateResponse, IState> = function(source: IStateResponse): IState {
  return {
    id: source.id,
    type: source.type,
    message: source.message,
    stateDetails: this.map('IStateDetailsResponse', source.state_details, 'IStateDetails'),
    data: source.data,
    timestamp: source.timestamp,
    name: source.name,
  }
}

export const mapIStateToIStateResponse: MapFunction<IState, IStateResponse> = function(source: IState): IStateResponse {
  return {
    'id': source.id,
    'type': source.type,
    'message': source.message,
    'state_details': this.map('IStateDetails', source.stateDetails, 'IStateDetailsResponse'),
    'data': source.data,
    'timestamp': source.timestamp,
    'name': source.name,
  }
}