var replace = require('replace')

replace({
  regex: 'packages/orion-design/src/index',
  replacement: '@prefecthq/orion-design',
  paths: [__dirname + '/../dist/index.d.ts'],
  recursive: false,
  silent: false
})
