export interface IFlowRunner {
  type: string,
  config: unknown,
}

export class FlowRunner implements IFlowRunner {
  public type: string
  public config: unknown

  public constructor(flowRunner: IFlowRunner) {
    this.type = flowRunner.type
    this.config = flowRunner.config
  }
}