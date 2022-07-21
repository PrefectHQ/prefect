module.exports = {
  root: true,
  env: {
    node: true
  },
  extends: ["@prefecthq"],
  parserOptions: {
    ecmaVersion: 2020,
    project: "./tsconfig.json"
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
