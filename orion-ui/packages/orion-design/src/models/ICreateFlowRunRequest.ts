import { StateType } from '@/models/StateType'

// this type is incomplete
// https://orion-docs.prefect.io/api-ref/rest-api/#/Deployments/create_flow_run_from_deployment_deployments__id__create_flow_run_post
export type ICreateFlowRunRequest = {
  state: {
    type: StateType,
    message: string,
  },
}