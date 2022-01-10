export class LogLevel {

  public static GetLabel(level: number): string {
    if (!LogLevel.Validate(level)) {
      throw 'Log level must be a number from 0 to 50'
    }

    const [first] = level.toString()

    switch (first) {
      case '5':
        return 'Critical'
      case '4':
        return 'Error'
      case '3':
        return 'Info'
      case '2':
        return 'Debug'
      default:
        return 'Not Set'
    }
  }

  public static Validate(level: number): boolean {
    return level >= 0 && level <= 50
  }
}