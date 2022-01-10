export interface State {
  id: string,
  type: string,
  message: string,
  state_details: Record<string, any>,
  data: Record<string, any>,
  timestamp: string,
  name: string,
}