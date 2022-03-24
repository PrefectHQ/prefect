import { dateProfile } from './Date'
import { deploymentProfile } from './Deployment'
import { empiricalPolicyProfile } from './EmpiricalPolicy'
import { flowProfile } from './Flow'
import { flowDataProfile } from './FlowData'
import { flowRunProfile } from './FlowRun'
import { flowRunGraphProfile } from './FlowRunGraph'
import { flowRunHistoryProfile } from './FlowRunHistory'
import { flowRunnerProfile } from './FlowRunner'
import { logsProfile } from './Logs'
import { scheduleProfile } from './Schedule'
import { stateProfile } from './State'
import { stateDetailsProfile } from './StateDetails'
import { stateHistoryProfile } from './StateHistory'
import { taskInputProfile, taskInputsProfile } from './TaskInput'
import { workQueueProfile } from './WorkQueue'
import { workQueueFilterProfile } from './WorkQueueFilter'

export const profiles = {
  'string:Date': dateProfile,
  'IDeploymentResponse:Deployment': deploymentProfile,
  'IEmpiricalPolicyResponse:EmpiricalPolicy': empiricalPolicyProfile,
  'IFlowResponse:Flow': flowProfile,
  'IFlowDataResponse:FlowData': flowDataProfile,
  'IFlowRunResponse:FlowRun': flowRunProfile,
  'IFlowRunGraphResponse:FlowRunGraph': flowRunGraphProfile,
  'IFlowRunHistoryResponse:RunHistory': flowRunHistoryProfile,
  'IFlowRunnerResponse:FlowRunner': flowRunnerProfile,
  'ILogResponse:Log': logsProfile,
  'IScheduleResponse:Schedule': scheduleProfile,
  'IStateResponse:IState': stateProfile,
  'IStateDetailResponse:IStateDetails': stateDetailsProfile,
  'IStateHistoryResponse:StateHistory': stateHistoryProfile,
  'ITaskInputResponse:TaskInput': taskInputProfile,
  'ITaskInputResponseRecord:TaskInputRecord': taskInputsProfile,
  'IWorkQueueResponse:WorkQueue': workQueueProfile,
  'IWorkQueueFilterResponse:WorkQueueFilter': workQueueFilterProfile,
}