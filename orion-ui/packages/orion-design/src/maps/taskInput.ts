import { isConstantTaskInputResponse, isParameterTaskInputResponse, isTaskRunTaskInputResponse, ITaskInputResponse } from '@/models/ITaskInputResponse'
import { ConstantTaskInput, ParameterTaskInput, TaskInput, TaskRunTaskInput } from '@/models/TaskInput'
import { MapFunction } from '@/services/Mapper'

export const mapITaskInputResponseToTaskInput: MapFunction<ITaskInputResponse, TaskInput> = function(source: ITaskInputResponse): TaskInput {
  if (isConstantTaskInputResponse(source)) {
    return new ConstantTaskInput({
      inputType: source.input_type,
      type: source.type,
    })
  }

  if (isParameterTaskInputResponse(source)) {
    return new ParameterTaskInput({
      inputType: source.input_type,
      name: source.name,
    })
  }

  if (isTaskRunTaskInputResponse(source)) {
    return new TaskRunTaskInput({
      inputType: source.input_type,
      id: source.id,
    })
  }

  throw 'Invalid ITaskInputResponse'
}

export const mapTaskInputToITaskInputResponse: MapFunction<TaskInput, ITaskInputResponse> = function(source: TaskInput): ITaskInputResponse {
  return {
    'input_type': source.inputType,
    'type': (source as ConstantTaskInput).type,
    'name': (source as ParameterTaskInput).name,
    'id': (source as TaskRunTaskInput).id,
  }
}