export interface IEmpiricalPolicy {
  maxRetries: number | null,
  retryDelaySeconds: number | null,
}

export class EmpiricalPolicy implements IEmpiricalPolicy {
  public maxRetries: number | null
  public retryDelaySeconds: number | null

  public constructor(empiricalPolicy: IEmpiricalPolicy) {
    this.maxRetries = empiricalPolicy.maxRetries
    this.retryDelaySeconds = empiricalPolicy.retryDelaySeconds
  }
}