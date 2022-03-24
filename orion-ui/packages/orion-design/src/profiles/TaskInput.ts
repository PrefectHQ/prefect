import { isConstantTaskInputResponse, isParameterTaskInputResponse, isTaskRunTaskInputResponse, ITaskInputResponse } from '@/models/ITaskInputResponse'
import { ConstantTaskInput, ParameterTaskInput, TaskInput, TaskRunTaskInput } from '@/models/TaskInput'
import { Profile, translate } from '@/services/Translate'

export const taskInputProfile: Profile<ITaskInputResponse, TaskInput> = {
  toDestination(source) {
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
  },
  toSource(destination) {
    return {
      'input_type': destination.inputType,
      'type': (destination as ConstantTaskInput).type,
      'name': (destination as ParameterTaskInput).name,
      'id': (destination as TaskRunTaskInput).id,
    }
  },
}

export const taskInputsProfile: Profile<Record<string, ITaskInputResponse[]>, Record<string, TaskInput[]>> = {
  toDestination(source) {
    const response = {} as Record<string, TaskInput[]>

    return Object.entries(source).reduce<Record<string, TaskInput[]>>((mapped, [key, value]) => {
      mapped[key] = value.map(x => (this as typeof translate).toDestination('ITaskInputResponse:TaskInput', x))

      return mapped
    }, response)
  },
  toSource(destination) {
    const response = {} as Record<string, ITaskInputResponse[]>

    return Object.entries(destination).reduce<Record<string, ITaskInputResponse[]>>((mapped, [key, value]) => {
      mapped[key] = value.map(x => (this as typeof translate).toSource('ITaskInputResponse:TaskInput', x))

      return mapped
    }, response)
  },
}