import { Toaster } from "@/components/ui/toaster";
import type { ReactRenderer } from "@storybook/react";
import type { DecoratorFunction } from "@storybook/types";

/**
 *
 * @example
 * ```ts
 * import { toastDecorator } from '@/storybook/utils'
 *
 * const meta: Meta<typeof MyComponentWithToast> = {
 * 	title: "UI/MyComponentWithToast",
 * 	decorators: [toastDecorator],
 * 	component: MyComponentWithToast,
 * };
 *
 * export default meta;
 */
export const toastDecorator: DecoratorFunction<ReactRenderer> = (Story) => (
	<>
		<Story />
		<Toaster />
	</>
);
