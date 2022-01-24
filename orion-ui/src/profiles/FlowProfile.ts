import Flow from '@/models/flow'
import { Profile } from 'packages/orion-design/src/profiles'

export class FlowProfile implements Profile<Flow> {
  public readonly key = 'flow'

  public generate(): Flow {
    return new Flow({
      id: '',
      created: new Date(),
      updated: new Date(),
      name: '',
      tags: []
    })
  }
}
