export type IScheduleResponse = IRRuleScheduleResponse | ICronScheduleResponse | IIntervalScheduleResponse

export type IRRuleScheduleResponse = {
  rrule: string,
  timezone: string | null,
}

export type ICronScheduleResponse = {
  cron: string,
  timezone: string | null,
  day_or: boolean | null,
}

export type IIntervalScheduleResponse = {
  interval: number,
  timezone: string | null,
  anchor_date: string | null,
}

export function isRRuleScheduleResponse(schedule: IScheduleResponse): schedule is IRRuleScheduleResponse {
  // eslint-disable-next-line no-prototype-builtins
  return schedule.hasOwnProperty('rrule')
}

export function isCronScheduleResponse(schedule: IScheduleResponse): schedule is ICronScheduleResponse {
  // eslint-disable-next-line no-prototype-builtins
  return schedule.hasOwnProperty('cron')
}

export function isIntervalScheduleResponse(schedule: IScheduleResponse): schedule is IIntervalScheduleResponse {
  // eslint-disable-next-line no-prototype-builtins
  return schedule.hasOwnProperty('interval')
}
