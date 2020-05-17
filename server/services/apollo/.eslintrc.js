module.exports = {
  root: true,
  env: {
    es6: true,
    node: true
  },
  extends: ['eslint:recommended', 'plugin:prettier/recommended'],
  parserOptions: {
    ecmaVersion: '2018',
    sourceType: 'module',
    parser: 'babel-eslint'
  },
  rules: {
    'no-console': 0,
    'linebreak-style': ['error', 'unix'],
    quotes: ['error', 'single'],
    semi: ['error', 'never'],
    'prettier/prettier': [
      'error',
      {
        singleQuote: true,
        semi: false,
        trailingComma: 'none'
      }
    ]
  },
  plugins: ['jest', 'prettier']
}
