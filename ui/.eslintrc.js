module.exports = {
  root: true,
  env: {
    node: true
  },
  extends: ["@prefecthq"],
  parser: 'vue-eslint-parser',
  parserOptions: {
    ecmaVersion: 2020,
    project: ["./tsconfig.json"],
    sourceType: 'module',
    parser: '@typescript-eslint/parser'
  },
  settings: {
    "import/resolver": {
      typescript: {
        project: "./tsconfig.json"
      }
    }
  },
  globals: {
    defineProps: 'readonly',
    defineEmits: 'readonly'
  }
}
