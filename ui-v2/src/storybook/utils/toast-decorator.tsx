import { Toaster } from "@/components/ui/toaster";
import { StoryFn } from "@storybook/react";

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
export const toastDecorator = (Story: StoryFn) => (
	<>
		{/** @ts-expect-error Error typing from React 19 types upgrade. Will need to wait for this up be updated */}
		<Story />
		<Toaster />
	</>
);
