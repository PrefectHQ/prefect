import type { Config } from '@jest/types'

const config: Config.InitialProjectOptions = {
  name: 'integration',
  displayName: 'Integration Tests',
  roots: ['<rootDir>'],
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {}],
    '.*\\.(vue)$': ['vue3-jest', {}]
  },
  moduleNameMapper: {
    '@/(.*)$': '<rootDir>/../../src/$1'
  },
  testEnvironment: 'jest-environment-puppeteer',
  globalSetup: './setup.js',
  globalTeardown: './teardown.js'
}

export default config
