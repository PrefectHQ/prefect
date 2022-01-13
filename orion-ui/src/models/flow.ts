export type IFlow = {
  id: string
  created: Date
  updated: Date
  name: string
  tags: string[]
}

export default class Flow {
  public readonly id: string
  public readonly created: Date
  public readonly updated: Date
  public name: string
  public tags: string[]

  constructor(flow: IFlow) {
    this.id = flow.id
    this.created = flow.created
    this.updated = flow.updated
    this.name = flow.name
    this.tags = flow.tags
  }
}
