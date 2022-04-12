import { mapStringToDate, mapDateToString } from './date'
import { mapDeploymentToIDeploymentResponse, mapIDeploymentResponseToDeployment } from './deployment'
import { mapEmpiricalPolicyToIEmpiricalPolicyResponse, mapIEmpiricalPolicyResponseToEmpiricalPolicy } from './empiricalPolicy'
import { mapFlowToIFlowResponse, mapIFlowResponseToFlow } from './flow'
import { mapFlowDataToIFlowDataResponse, mapIFlowDataResponseToFlowData } from './flowData'
import { mapFlowRunToIFlowRunResponse, mapIFlowRunResponseToFlowRun } from './flowRun'
import { mapFlowRunGraphToIFlowRunGraphResponse, mapIFlowRunGraphResponseToFlowRunGraph } from './flowRunGraph'
import { mapRunHistoryToIFlowRunHistoryResponse, mapIFlowRunHistoryResponseToRunHistory } from './flowRunHistory'
import { mapFlowRunnerToIFlowRunnerResponse, mapIFlowRunnerResponseToFlowRunner } from './flowRunner'
import { mapLogToILogResponse, mapILogResponseToLog } from './logs'
import { mapNumberToString, mapStringToNumber } from './number'
import { mapUiFlowRunHistoryToScatterPlotItem } from './scatterPlotItem'
import { mapScheduleToIScheduleResponse, mapIScheduleResponseToSchedule } from './schedule'
import { mapIStateResponseToIState, mapIStateToIStateResponse } from './state'
import { mapIStateDetailsResponseToIStateDetails, mapIStateDetailsToIStateDetailsResponse } from './stateDetails'
import { mapStateHistoryToIStateHistoryResponse, mapIStateHistoryResponseToStateHistory } from './stateHistory'
import { mapTaskInputToITaskInputResponse, mapITaskInputResponseToTaskInput } from './taskInput'
import { mapTaskRunToITaskRunResponse, mapITaskRunResponseToTaskRun } from './taskRun'
import { mapUiFlowRunHistoryResponseToUiFlowRunHistory } from './uiFlowRunHistory'
import { mapWorkQueueToIWorkQueueResponse, mapIWorkQueueResponseToWorkQueue } from './workQueue'
import { mapWorkQueueFilterToIWorkQueueFilterResponse, mapIWorkQueueFilterResponseToWorkQueueFilter } from './workQueueFilter'

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
  UiFlowRunHistoryResponse: {
    UiFlowRunHistory: mapUiFlowRunHistoryResponseToUiFlowRunHistory,
  },
  UiFlowRunHistory: {
    ScatterPlotItem: mapUiFlowRunHistoryToScatterPlotItem,
  },
}