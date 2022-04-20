import type { Config } from '@jest/types'

// todo: make a mocks folder and import them all in a barrel? globals: { ...mocks }
class DOMRect {}

const config: Config.InitialOptions = {
  projects: ['./test-projects/*'],
  maxWorkers: 1,
  moduleFileExtensions: ['js', 'ts', 'json', 'vue'],
  rootDir: '.',
  testURL: 'http://localhost/',
  verbose: true,
  globals: {
    DOMRect,
    'ts-jest': {
      tsconfig: './tsconfig.json',
    },
  },
}

export default config
