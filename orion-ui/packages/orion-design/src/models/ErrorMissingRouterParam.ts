export class ErrorMissingRouterParam extends Error {
  public constructor(param: string) {
    super(`Expected param ${param} in route but no value was found.`)
  }
}