export type IScheduleResponse = IRRuleScheduleResponse | ICronScheduleResponse | IIntervalScheduleResponse

export type IRRuleScheduleResponse = {
  type: 'rrule',
  rrule: string,
  timezone: string | null,
}

export type ICronScheduleResponse = {
  type: 'cron',
  cron: string,
  timezone: string | null,
  day_or: boolean | null,
}

export type IIntervalScheduleResponse = {
  type: 'interval',
  interval: number,
  timezone: string | null,
  anchor_date: string | null,
}

export function isRRuleScheduleResponse(schedule: IScheduleResponse): schedule is IRRuleScheduleResponse {
  return schedule.type === 'rrule'
}

export function isCronScheduleResponse(schedule: IScheduleResponse): schedule is ICronScheduleResponse {
  return schedule.type === 'cron'
}

export function isIntervalScheduleResponse(schedule: IScheduleResponse): schedule is IIntervalScheduleResponse {
  return schedule.type === 'interval'
}
