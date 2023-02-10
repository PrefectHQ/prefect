export function timeout(ms = 0): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
