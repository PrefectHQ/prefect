export class SimpleIdManager {
  private next: number = 1

  public get(): number {
    return this.next++
  }
}
