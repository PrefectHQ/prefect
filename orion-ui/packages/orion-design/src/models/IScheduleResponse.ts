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
  return !!(schedule as IRRuleScheduleResponse).rrule
}

export function isCronScheduleResponse(schedule: IScheduleResponse): schedule is ICronScheduleResponse {
  return !!(schedule as ICronScheduleResponse).cron
}

export function isIntervalScheduleResponse(schedule: IScheduleResponse): schedule is IIntervalScheduleResponse {
  return !!(schedule as IIntervalScheduleResponse).interval
}
