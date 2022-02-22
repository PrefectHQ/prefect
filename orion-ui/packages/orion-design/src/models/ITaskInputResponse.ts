export type ITaskInputResponse = {
  input_type: 'constant' | 'parameter' | 'task_run',
  type?: string,
  name?: string,
  id?: string,
}