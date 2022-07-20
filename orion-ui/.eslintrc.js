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
  rules: {
    "vue/multi-word-component-names": "off",
    "vue/no-static-inline-styles": "off",
    "@typescript-eslint/no-unnecessary-condition": "off"
  },
  globals: {
    defineProps: 'readonly',
    defineEmits: 'readonly'
  }
}
