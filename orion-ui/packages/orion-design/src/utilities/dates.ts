// duplicate imports are necessary for datefns tree shaking
/* eslint-disable import/no-duplicates */
import format from 'date-fns/format'
import parse from 'date-fns/parse'

const dateTimeNumericFormat = 'yyyy/MM/dd hh:mm:ss a'
const timeNumericFormat = 'hh:mm:ss a'
const dateFormat = 'MMM do, yyyy'

export function formatDateTimeNumeric(date: Date | string): string {
  const parsed = new Date(date)

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
