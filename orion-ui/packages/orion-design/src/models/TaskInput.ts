export interface ITaskInput {
  inputType: 'constant' | 'parameter' | 'task_run',
  type?: string,
  name?: string,
  id?: string,
}

export type IConstantTaskInput = Pick<ITaskInput, 'type'> & { inputType: 'constant' }
export type IParameterTaskInput = Pick<ITaskInput, 'name'> & { inputType: 'parameter' }
export type ITaskRunTaskInput = Pick<ITaskInput, 'id'> & { inputType: 'task_run' }

export function isConstantTaskInput(taskInput: ITaskInput): taskInput is IConstantTaskInput {
  return taskInput.inputType === 'constant'
}

export function isParameterTaskInput(taskInput: ITaskInput): taskInput is IParameterTaskInput {
  return taskInput.inputType === 'parameter'
}

export function isTaskRunTaskInput(taskInput: ITaskInput): taskInput is ITaskRunTaskInput {
  return taskInput.inputType === 'task_run'
}

export class TaskInput implements ITaskInput {
  public inputType: 'constant' | 'parameter' | 'task_run'
  public type?: string
  public name?: string
  public id?: string

  public constructor(taskInput: ITaskInput) {
    this.inputType = taskInput.inputType

    if (isConstantTaskInput(taskInput)) {
      this.type = taskInput.type
    }

    if (isParameterTaskInput(taskInput)) {
      this.name = taskInput.name
    }

    if (isTaskRunTaskInput(taskInput)) {
      this.id = taskInput.id
    }
  }
}