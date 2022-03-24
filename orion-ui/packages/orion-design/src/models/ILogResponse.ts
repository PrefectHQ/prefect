export type ILogResponse = {
  id: string,
  created: string,
  updated: string,
  name: string,
  level: number,
  message: string,
  timestamp: string,
  flow_run_id: string,
  task_run_id: string,
}