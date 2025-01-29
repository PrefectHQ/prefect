import type { ReactRenderer } from "@storybook/react";
import type { DecoratorFunction } from "@storybook/types";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

const queryClient = new QueryClient();

/**
 *
 * @example
 * ```ts
 * import { reactQueryDecorator } from '@/storybook/utils'
 *
 * const meta: Meta<typeof MyComponent> = {
 * 	title: "UI/MyComponent",
 * 	decorators: [reactQueryDecorator],
 * 	component: MyComponent,
 * };
 *
 * export default meta;
 */
export const reactQueryDecorator: DecoratorFunction<ReactRenderer> = (
	Story,
) => (
	<QueryClientProvider client={queryClient}>
		<Story />
		<ReactQueryDevtools />
	</QueryClientProvider>
);
