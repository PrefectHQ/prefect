import { MockGenerator } from '.'

export const randomString: MockGenerator<string> = () => {
  return (Math.random() + 1).toString(36).substring(7)
}