export class Settings {
  private static _apiUrl: string | null = null

  public static get apiUrl(): string {
    if (this._apiUrl === null) {
      throw 'Settings.apiUrl is not set'
    }

    return this._apiUrl
  }

  public static set apiUrl(port: string) {
    this._apiUrl = port
  }
}