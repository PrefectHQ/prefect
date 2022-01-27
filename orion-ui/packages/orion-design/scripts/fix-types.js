var replace = require('replace')

replace({
  regex: 'packages/orion-design/src/index',
  replacement: '@prefecthq/orion-design',
  paths: [__dirname + '/../dist/index.d.ts'],
  recursive: false,
  silent: false
})

replace({
  regex: 'packages/orion-design/src/components/index',
  replacement: '@prefecthq/orion-design/components',
  paths: [__dirname + '/../dist/index.d.ts'],
  recursive: false,
  silent: false
})

replace({
  regex: 'packages/orion-design/src/services/index',
  replacement: '@prefecthq/orion-design/services',
  paths: [__dirname + '/../dist/index.d.ts'],
  recursive: false,
  silent: false
})

replace({
  regex: 'packages/orion-design/src/utilities/index',
  replacement: '@prefecthq/orion-design/utilities',
  paths: [__dirname + '/../dist/index.d.ts'],
  recursive: false,
  silent: false
})

replace({
  regex: 'packages/orion-design/src/models/index',
  replacement: '@prefecthq/orion-design/models',
  paths: [__dirname + '/../dist/index.d.ts'],
  recursive: false,
  silent: false
})

replace({
  regex: 'packages/orion-design/src/types/index',
  replacement: '@prefecthq/orion-design/types',
  paths: [__dirname + '/../dist/index.d.ts'],
  recursive: false,
  silent: false
})
