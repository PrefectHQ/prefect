export type IFlow = {
  id: string,
  created: Date,
  updated: Date,
  name: string,
  tags: string[],
}

export class Flow implements IFlow {
  public readonly id: string
  public readonly created: Date
  public readonly updated: Date
  public name: string
  public tags: string[]

  public constructor(flow: IFlow) {
    this.id = flow.id
    this.created = flow.created
    this.updated = flow.updated
    this.name = flow.name
    this.tags = flow.tags
  }
}
