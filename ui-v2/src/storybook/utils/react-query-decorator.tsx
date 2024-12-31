import { StoryFn } from "@storybook/react";
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
export const reactQueryDecorator = (Story: StoryFn) => (
	<QueryClientProvider client={queryClient}>
		{/** @ts-expect-error Error typing from React 19 types upgrade. Will need to wait for this up be updated */}
		<Story />
		<ReactQueryDevtools />
	</QueryClientProvider>
);
