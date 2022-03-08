// duplicate imports are necessary for datefns tree shaking
/* eslint-disable import/no-duplicates */
import { formatInTimeZone } from 'date-fns-tz'
import format from 'date-fns/format'
import parse from 'date-fns/parse'

const dateTimeNumericFormat = 'yyyy/MM/dd hh:mm:ss a'
const timeNumericFormat = 'hh:mm:ss a'
const dateFormat = 'MMM do, yyyy'
const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone

export function formatDateTimeNumeric(date: Date | string): string {
  const parsed = new Date(date)
  console.log(format(parsed, dateTimeNumericFormat))
  return format(parsed, dateTimeNumericFormat)
}

export function parseDateTimeNumeric(input: string, reference: Date = new Date()): Date {
  return parse(input, dateTimeNumericFormat, reference)
}

export function formatTimeNumeric(date: Date | string): string {
  const parsed = new Date(date)

  return format(parsed, timeNumericFormat)
}

export function parseTimeNumeric(input: string, reference: Date = new Date()): Date {
  return parse(input, timeNumericFormat, reference)
}

export function formatDate(date: Date | string): string {
  const parsed = new Date(date)

  return format(parsed, dateFormat)
}

export function parseDate(input: string, reference: Date = new Date()): Date {
  return parse(input, dateFormat, reference)
}

export function formatDateTimeNumericInTimeZone(date: Date | string, timezone: string = localTimezone): string {
  return formatInTimeZone(date, timezone, dateTimeNumericFormat)
}

export function formatTimeNumericInTimeZone(date: Date | string, timezone: string = localTimezone): string {
  return formatInTimeZone(date, timezone, timeNumericFormat)
}

export function formatDateInTimeZone(date: Date | string, timezone: string = localTimezone): string {
  return formatInTimeZone(date, timezone, dateFormat)
}