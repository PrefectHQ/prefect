export type ITaskInputResponse = IConstantTaskInputResponse | IParameterTaskInputResponse | ITaskRunTaskInputResponse

export type IConstantTaskInputResponse = {
  input_type: 'constant',
  type: string,
}

export type IParameterTaskInputResponse = {
  input_type: 'parameter',
  name: string,
}

export type ITaskRunTaskInputResponse = {
  input_type: 'task_run',
  id: string,
}

export function isConstantTaskInputResponse(taskInputResponse: ITaskInputResponse): taskInputResponse is IConstantTaskInputResponse {
  return taskInputResponse.input_type === 'constant'
}

export function isParameterTaskInputResponse(taskInputResponse: ITaskInputResponse): taskInputResponse is IParameterTaskInputResponse {
  return taskInputResponse.input_type === 'parameter'
}

export function isTaskRunTaskInputResponse(taskInputResponse: ITaskInputResponse): taskInputResponse is ITaskRunTaskInputResponse {
  return taskInputResponse.input_type === 'task_run'
}