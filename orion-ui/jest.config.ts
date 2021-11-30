import type { Config } from '@jest/types'

// todo: make a mocks folder and import them all in a barrel? globals: { ...mocks }
class DOMRect {}

const config: Config.InitialOptions = {
  maxWorkers: 1,
  moduleFileExtensions: ['js', 'ts', 'json', 'vue'],
  rootDir: '.',
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {}], // process `*.ts` files with ts-jest
    '.*\\.(vue)$': ['vue3-jest', {}] // process `*.vue` files with vue-jest
  },
  testURL: 'http://localhost/',
  setupFiles: ['./tests/setupJest.ts'],
  verbose: true,
  testEnvironment: 'jsdom',
  globals: {
    DOMRect
  }
}

export default config
