export interface IDeployment {
  id: string,
  created: Date,
  updated: Date,
  name: string,
  flowId: string,
  flowData: Record<string, any> | null,
  schedule: Record<string, any> | null,
  isScheduleActive: boolean,
  parameters: Record<string, any> | null,
  tags: string[],
}

export class Deployment implements IDeployment {
  public readonly id: string
  public created: Date
  public updated: Date
  public name: string
  public readonly flowId: string
  public flowData: Record<string, any> | null
  public schedule: Record<string, any> | null
  public isScheduleActive: boolean
  public parameters: Record<string, any> | null
  public tags: string[]

  constructor(deployment: IDeployment) {
    this.id = deployment.id
    this.created = deployment.created
    this.updated = deployment.updated
    this.name = deployment.name
    this.flowId = deployment.flowId
    this.flowData = deployment.flowData
    this.schedule = deployment.schedule
    this.isScheduleActive = deployment.isScheduleActive
    this.parameters = deployment.parameters
    this.tags = deployment.tags
  }
}