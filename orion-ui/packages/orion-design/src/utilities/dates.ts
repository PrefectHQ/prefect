import { format } from 'date-fns'

export function formatDateTimeNumeric(date: Date | string): string {
  const parsed = new Date(date)

  return format(parsed, 'yyyy/MM/dd hh:mm:ss a')
}

export function formatTimeNumeric(date: Date | string): string {
  const parsed = new Date(date)

  return format(parsed, 'hh:mm:ss a')
}
