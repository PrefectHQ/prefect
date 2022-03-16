export interface IFlowData {
  encoding: string,
  blob: string,
}

export class FlowData implements IFlowData {
  public encoding: string
  public blob: string

  public constructor(flowData: IFlowData) {
    this.encoding = flowData.encoding
    this.blob = flowData.blob
  }
}