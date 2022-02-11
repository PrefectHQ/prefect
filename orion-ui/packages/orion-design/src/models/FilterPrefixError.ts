export class FilterPrefixError extends Error {
  public constructor() {
    super('filter has an invalid prefix')
  }
}