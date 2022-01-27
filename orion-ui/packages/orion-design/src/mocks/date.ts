export function randomDate(start?: Date, end?: Date): Date {
  if (!start) {
    start = new Date(0)
  }

  if (!end) {
    end = new Date()
  }

  return new Date(start.getTime() + Math.random() * (end.getTime() - start.getTime()))
}