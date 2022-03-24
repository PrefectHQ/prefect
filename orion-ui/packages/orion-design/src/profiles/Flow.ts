import { Flow } from '@/models/Flow'
import { IFlowResponse } from '@/models/IFlowResponse'
import { Profile } from '@/services/Translate'

export const flowProfile: Profile<IFlowResponse, Flow> = {
  toDestination(source) {
    return new Flow({
      id: source.id,
      name: source.name,
      tags: source.tags,
      created: new Date(source.created),
      updated: new Date(source.updated),
    })
  },
  toSource(destination) {
    return {
      id: destination.id,
      name: destination.name,
      tags: destination.tags,
      created: destination.created.toISOString(),
      updated: destination.updated.toISOString(),
    }
  },
}