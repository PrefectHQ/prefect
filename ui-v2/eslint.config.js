import js from "@eslint/js";
import pluginQuery from "@tanstack/eslint-plugin-query";
import pluginRouter from "@tanstack/eslint-plugin-router";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import testingLibrary from "eslint-plugin-testing-library";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
	{ ignores: ["dist", "src/api/prefect.ts", "e2e/**", "playwright.config.ts"] },
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
			"react/prop-types": "off",
			"no-restricted-syntax": [
				"warn",
				{
					selector: "Literal[value=/(?:^|\\s)(?:bg|text|border)-gray-\\d/]",
					message:
						"Avoid hardcoded gray color classes. Use semantic tokens (e.g. bg-muted, text-muted-foreground) for dark mode compatibility.",
				},
				{
					selector:
						"Literal[value=/(?:^|\\s)(?:bg|text|border)-(?:red|green|blue|yellow|orange|purple|sky)-\\d/]",
					message:
						"Avoid hardcoded color classes. Use semantic state color tokens (e.g. bg-state-completed-500) for dark mode compatibility.",
				},
				{
					selector: "Literal[value=/(?:^|\\s)(?:bg-white|bg-black)(?:\\s|$)/]",
					message:
						"Avoid bg-white/bg-black. Use semantic tokens (e.g. bg-background, bg-foreground) for dark mode compatibility.",
				},
			],
		},
	},
	...pluginQuery.configs["flat/recommended"],
	...pluginRouter.configs["flat/recommended"],
	{
		files: ["src/components/code-banner/**/*.{ts,tsx}"],
		rules: {
			"no-restricted-syntax": "off",
		},
	},
	{
		files: ["tests/**/*.{ts,tsx}"],
		plugins: testingLibrary.configs["flat/react"].plugins,
		rules: {
			...testingLibrary.configs["flat/react"].rules,
		},
	},
);
