import type { Config } from '@jest/types'

process.env.VUE_CLI_BABEL_TARGET_NODE = true as unknown as string
process.env.VUE_CLI_BABEL_TRANSPILE_MODULES = true as unknown as string

// Sync object
const config: Config.InitialOptions = {
  maxWorkers: 1,
  moduleFileExtensions: ['js', 'ts', 'json', 'vue'],
  rootDir: '.',
  transform: {
    '^.+\\.js$': ['babel-jest', {}],
    '^.+\\.tsx?$': ['ts-jest', {}], // process `*.ts` files with ts-jest
    '.*\\.(vue)$': ['vue-jest', {}] // process `*.vue` files with vue-jest
  },
  moduleNameMapper: {
    '\\.(css|scss)$': '<rootDir>/tests/__mocks__/styleMock.js'
  },
  testURL: 'http://localhost/',
  setupFiles: ['./tests/setupJest.js'],
  verbose: true
}

export default config
