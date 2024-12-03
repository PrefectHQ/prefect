import js from "@eslint/js";
import pluginRouter from "@tanstack/eslint-plugin-router";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";
import testingLibrary from "eslint-plugin-testing-library";
import jestDom from "eslint-plugin-jest-dom";
import pluginQuery from "@tanstack/eslint-plugin-query";

export default tseslint.config(
	{ ignores: ["dist", "src/api/prefect.ts"] },
	{
		extends: [
			js.configs.recommended,
			...tseslint.configs.recommendedTypeChecked,
		],
		files: ["**/*.{ts,tsx}"],
		languageOptions: {
			ecmaVersion: 2020,
			globals: globals.browser,
			parserOptions: {
				project: ["./tsconfig.node.json", "./tsconfig.app.json"],
				tsconfigRootDir: import.meta.dirname,
			},
		},
		settings: {
			react: {
				version: "18.3",
			},
		},
		plugins: {
			react,
			"react-hooks": reactHooks,
			"react-refresh": reactRefresh,
		},
		rules: {
			...reactHooks.configs.recommended.rules,
			"react-refresh/only-export-components": [
				"warn",
				{ allowConstantExport: true },
			],
			...react.configs.recommended.rules,
			...react.configs["jsx-runtime"].rules,
		},
	},
	...pluginQuery.configs["flat/recommended"],
	...pluginRouter.configs["flat/recommended"],
	{
		files: ["tests/**/*.{ts,tsx}"],
		...testingLibrary.configs["flat/react"],
		...jestDom.configs["flat/recommended"],
	},
);
