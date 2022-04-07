import { mapStringToDate, mapDateToString } from './Date'
import { mapDeploymentToIDeploymentResponse, mapIDeploymentResponseToDeployment } from './Deployment'
import { mapEmpiricalPolicyToIEmpiricalPolicyResponse, mapIEmpiricalPolicyResponseToEmpiricalPolicy } from './EmpiricalPolicy'
import { mapFlowToIFlowResponse, mapIFlowResponseToFlow } from './Flow'
import { mapFlowDataToIFlowDataResponse, mapIFlowDataResponseToFlowData } from './FlowData'
import { mapFlowRunToIFlowRunResponse, mapIFlowRunResponseToFlowRun } from './FlowRun'
import { mapFlowRunGraphToIFlowRunGraphResponse, mapIFlowRunGraphResponseToFlowRunGraph } from './FlowRunGraph'
import { mapRunHistoryToIFlowRunHistoryResponse, mapIFlowRunHistoryResponseToRunHistory } from './FlowRunHistory'
import { mapFlowRunnerToIFlowRunnerResponse, mapIFlowRunnerResponseToFlowRunner } from './FlowRunner'
import { mapLogToILogResponse, mapILogResponseToLog } from './Logs'
import { mapNumberToString, mapStringToNumber } from './Number'
import { mapScheduleToIScheduleResponse, mapIScheduleResponseToSchedule } from './Schedule'
import { mapIStateResponseToIState, mapIStateToIStateResponse } from './State'
import { mapIStateDetailsResponseToIStateDetails, mapIStateDetailsToIStateDetailsResponse } from './StateDetails'
import { mapStateHistoryToIStateHistoryResponse, mapIStateHistoryResponseToStateHistory } from './StateHistory'
import { mapTaskInputToITaskInputResponse, mapITaskInputResponseToTaskInput } from './TaskInput'
import { mapTaskRunToITaskRunResponse, mapITaskRunResponseToTaskRun } from './TaskRun'
import { mapWorkQueueToIWorkQueueResponse, mapIWorkQueueResponseToWorkQueue } from './WorkQueue'
import { mapWorkQueueFilterToIWorkQueueFilterResponse, mapIWorkQueueFilterResponseToWorkQueueFilter } from './WorkQueueFilter'

export const maps = {
  string: {
    Date: mapStringToDate,
    number: mapStringToNumber,
  },
  Date: {
    string: mapDateToString,
  },
  Deployment: {
    IDeploymentResponse: mapDeploymentToIDeploymentResponse,
  },
  IDeploymentResponse: {
    Deployment: mapIDeploymentResponseToDeployment,
  },
  EmpiricalPolicy: {
    IEmpiricalPolicyResponse: mapEmpiricalPolicyToIEmpiricalPolicyResponse,
  },
  IEmpiricalPolicyResponse: {
    EmpiricalPolicy: mapIEmpiricalPolicyResponseToEmpiricalPolicy,
  },
  Flow: {
    IFlowResponse: mapFlowToIFlowResponse,
  },
  IFlowResponse: {
    Flow: mapIFlowResponseToFlow,
  },
  FlowData: {
    IFlowDataResponse: mapFlowDataToIFlowDataResponse,
  },
  IFlowDataResponse: {
    FlowData: mapIFlowDataResponseToFlowData,
  },
  FlowRun: {
    IFlowRunResponse: mapFlowRunToIFlowRunResponse,
  },
  IFlowRunResponse: {
    FlowRun: mapIFlowRunResponseToFlowRun,
  },
  FlowRunGraph: {
    IFlowRunGraphResponse: mapFlowRunGraphToIFlowRunGraphResponse,
  },
  IFlowRunGraphResponse: {
    FlowRunGraph: mapIFlowRunGraphResponseToFlowRunGraph,
  },
  RunHistory: {
    IFlowRunHistoryResponse: mapRunHistoryToIFlowRunHistoryResponse,
  },
  IFlowRunHistoryResponse: {
    RunHistory: mapIFlowRunHistoryResponseToRunHistory,
  },
  FlowRunner: {
    IFlowRunnerResponse: mapFlowRunnerToIFlowRunnerResponse,
  },
  IFlowRunnerResponse: {
    FlowRunner: mapIFlowRunnerResponseToFlowRunner,
  },
  Log: {
    ILogResponse: mapLogToILogResponse,
  },
  ILogResponse: {
    Log: mapILogResponseToLog,
  },
  number: {
    string: mapNumberToString,
  },
  Schedule: {
    IScheduleResponse: mapScheduleToIScheduleResponse,
  },
  IScheduleResponse: {
    Schedule: mapIScheduleResponseToSchedule,
  },
  IStateResponse: {
    IState: mapIStateResponseToIState,
  },
  IState: {
    IStateResponse: mapIStateToIStateResponse,
  },
  IStateDetailsResponse: {
    IStateDetails: mapIStateDetailsResponseToIStateDetails,
  },
  IStateDetails: {
    IStateDetailsResponse: mapIStateDetailsToIStateDetailsResponse,
  },
  StateHistory: {
    IStateHistoryResponse: mapStateHistoryToIStateHistoryResponse,
  },
  IStateHistoryResponse: {
    StateHistory: mapIStateHistoryResponseToStateHistory,
  },
  TaskInput: {
    ITaskInputResponse: mapTaskInputToITaskInputResponse,
  },
  ITaskInputResponse: {
    TaskInput: mapITaskInputResponseToTaskInput,
  },
  TaskRun: {
    ITaskRunResponse: mapTaskRunToITaskRunResponse,
  },
  ITaskRunResponse: {
    TaskRun: mapITaskRunResponseToTaskRun,
  },
  WorkQueue: {
    IWorkQueueResponse: mapWorkQueueToIWorkQueueResponse,
  },
  IWorkQueueResponse: {
    WorkQueue: mapIWorkQueueResponseToWorkQueue,
  },
  WorkQueueFilter: {
    IWorkQueueFilterResponse: mapWorkQueueFilterToIWorkQueueFilterResponse,
  },
  IWorkQueueFilterResponse: {
    WorkQueueFilter: mapIWorkQueueFilterResponseToWorkQueueFilter,
  },
}