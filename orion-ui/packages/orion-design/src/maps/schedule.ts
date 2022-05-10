import { IScheduleResponse, isCronScheduleResponse, isIntervalScheduleResponse, isRRuleScheduleResponse } from '@/models/IScheduleResponse'
import { CronSchedule, IntervalSchedule, RRuleSchedule, Schedule } from '@/models/Schedule'
import { MapFunction } from '@/services/Mapper'

export const mapIScheduleResponseToSchedule: MapFunction<IScheduleResponse, Schedule> = function(source: IScheduleResponse): Schedule {
  if (isRRuleScheduleResponse(source)) {
    return new RRuleSchedule({
      timezone: source.timezone,
      rrule: source.rrule,
    })
  }

  if (isCronScheduleResponse(source)) {
    return new CronSchedule({
      timezone: source.timezone,
      cron: source.cron,
      dayOr: source.day_or,
    })
  }

  if (isIntervalScheduleResponse(source)) {
    return new IntervalSchedule({
      timezone: source.timezone,
      interval: source.interval,
      anchorDate: source.anchor_date,
    })
  }

  throw 'Invalid IScheduleResponse'
}

export const mapScheduleToIScheduleResponse: MapFunction<Schedule, IScheduleResponse> = function(source: Schedule): IScheduleResponse {
  return {
    'timezone': source.timezone,
    'rrule': (source as RRuleSchedule).rrule,
    'cron': (source as CronSchedule).cron,
    'day_or': (source as CronSchedule).dayOr,
    'interval': (source as IntervalSchedule).interval,
    'anchor_date': (source as IntervalSchedule).anchorDate,
  }
}