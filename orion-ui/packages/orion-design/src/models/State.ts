export interface IState {
  id: string,
  type: string,
  message: string,
  stateDetails: Record<string, unknown>,
  data: Record<string, unknown>,
  timestamp: string,
  name: string,
}