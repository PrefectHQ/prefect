import type { Config } from '@jest/types'

const config: Config.InitialProjectOptions = {
  name: 'unit',
  displayName: 'Unit Tests',
  rootDir: '.',
  roots: ['<rootDir>/tests/'],
  testEnvironment: 'jsdom',
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {}],
    '.*\\.(vue)$': ['vue3-jest', {}],
  },
  moduleNameMapper: {
    '@/(.*)$': '<rootDir>/../../src/$1',
  },
  setupFiles: ['./setup.ts'],
}

export default config
