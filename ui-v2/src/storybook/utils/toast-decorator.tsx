import type { ReactRenderer } from "@storybook/react";
import type { DecoratorFunction } from "storybook/internal/types";
import { Toaster } from "@/components/ui/sonner";

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
