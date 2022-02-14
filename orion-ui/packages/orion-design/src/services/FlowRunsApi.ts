import { Api } from './Api'

export type IFlowRunResponse = {
  name: 'string',
}

export class FlowRunsApi extends Api {

  protected route: string = '/api/flow_runs'

  public getFlowRun(id: string): Promise<IFlowRunResponse> {
    return this.get<IFlowRunResponse>(`/${id}`).then(response => response.data)
  }

}

export const flowRunsApi = new FlowRunsApi()