import { withThemeByClassName } from "@storybook/addon-themes";
import type { Preview } from "@storybook/react";
import { handlers } from "@tests/utils/handlers";
import { setupWorker } from "msw/browser";
import { mswLoader } from "msw-storybook-addon/csf3";

import "../src/index.css";

export default {
	parameters: {
		controls: {
			matchers: {
				color: /(background|color)$/i,
				date: /Date$/i,
			},
		},
	},
	decorators: [
		withThemeByClassName({
			themes: {
				Light: "",
				Dark: "dark",
			},
			defaultTheme: "Light",
		}),
	],
	// Provide the MSW addon loader globally
	loaders: [
		mswLoader(async () => {
			const worker = setupWorker(...handlers);
			await worker.start({ onUnhandledRequest: "bypass" });
			return worker;
		}),
	],
} satisfies Preview;
