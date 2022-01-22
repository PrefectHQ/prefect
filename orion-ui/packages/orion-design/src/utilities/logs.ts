export function logLevelLabel(level: number): string {
  const [first] = level.toString()

  switch (first) {
    case '5':
      return 'Critical'
    case '4':
      return 'Error'
    case '3':
      return 'Warning'
    case '2':
      return 'Info'
    case '1':
      return 'Debug'
    default:
      return 'Not Set'
  }
}