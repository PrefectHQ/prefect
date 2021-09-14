module.exports = {
  root: true,
  env: {
    node: true
  },
  extends: [
    'plugin:vue/vue3-essential',
    'eslint:recommended',
    '@vue/typescript/recommended',
    '@vue/prettier',
    '@vue/prettier/@typescript-eslint'
  ],
  parserOptions: {
    ecmaVersion: 2020
  },
  rules: {
    'no-console': process.env.NODE_ENV === 'production' ? 'error' : 'off',
    'no-debugger': process.env.NODE_ENV === 'production' ? 'error' : 'off',
    'prettier/prettier': [
      'error',
      {
        singleQuote: true,
        semi: false,
        trailingComma: 'none',
        useTabs: false,
        printWidth: 80,
        htmlWhitespaceSensitivity: 'strict'
      }
    ],
    quotes: ['error', 'single', { avoidEscape: true }],
    semi: ['error', 'never'],
    'vue/valid-v-slot': 'off',
    '@typescript-eslint/no-inferrable-types': [
      'off',
      {
        ignoreProperties: true
      }
    ]
  },
  overrides: [
    {
      files: [
        '**/__tests__/*.{j,t}s?(x)',
        '**/tests/unit/**/*.spec.{j,t}s?(x)'
      ],
      env: {
        'jest/globals': true
      }
    }
  ]
}
