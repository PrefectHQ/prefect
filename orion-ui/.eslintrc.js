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
    "@typescript-eslint/no-explicit-any": "off",
    "vue/multi-word-component-names": "off",
    "vue/no-static-inline-styles": "off"
  },
  globals: {
    defineProps: 'readonly',
    defineEmits: 'readonly'
  }
}
