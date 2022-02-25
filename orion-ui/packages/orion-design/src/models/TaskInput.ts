/* eslint-disable max-classes-per-file */
export type ITaskInput = IConstantTaskInput | IParameterTaskInput | ITaskRunTaskInput
export type TaskInput = ConstantTaskInput | ParameterTaskInput | TaskRunTaskInput

export type IConstantTaskInput = {
  inputType: 'constant',
  type: string,
}

export type IParameterTaskInput = {
  inputType: 'parameter',
  name: string,
}

export type ITaskRunTaskInput = {
  inputType: 'task_run',
  id: string,
}

export class ConstantTaskInput implements IConstantTaskInput {
  public readonly inputType: 'constant'
  public type: string

  public constructor(taskInput: IConstantTaskInput) {
    this.inputType = taskInput.inputType
    this.type = taskInput.type
  }
}

export class ParameterTaskInput implements IParameterTaskInput {
  public readonly inputType: 'parameter'
  public name: string

  public constructor(taskInput: IParameterTaskInput) {
    this.inputType = taskInput.inputType
    this.name = taskInput.name
  }
}

export class TaskRunTaskInput implements ITaskRunTaskInput {
  public readonly inputType: 'task_run'
  public id: string

  public constructor(taskInput: ITaskRunTaskInput) {
    this.inputType = taskInput.inputType
    this.id = taskInput.id
  }
}