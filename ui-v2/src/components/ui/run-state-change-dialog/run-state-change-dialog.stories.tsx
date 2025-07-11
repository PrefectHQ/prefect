import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { toast } from "sonner";
import { StateBadge } from "@/components/ui/state-badge";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import { RunStateChangeDialog } from "./run-state-change-dialog";

const baseState = {
	id: "test-state-id",
	type: "COMPLETED",
	name: "Completed",
	message: "Run completed successfully",
} as const;

const meta = {
	title: "UI/RunStateChangeDialog",
	component: RunStateChangeDialog,
	parameters: {
		layout: "centered",
	},
	decorators: [reactQueryDecorator, toastDecorator],
} satisfies Meta<typeof RunStateChangeDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Success: Story = {
	args: {
		currentState: baseState,
		open: true,
		onOpenChange: () => {},
		title: "Change Flow Run State",
		onSubmitChange: (values) => {
			toast.success(
				<div className="flex items-center gap-2">
					Flow run state changed to{" "}
					<StateBadge type={values.state} name={values.state} />
				</div>,
			);
			return Promise.resolve();
		},
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/:id/set_state"), () => {
					return HttpResponse.json({
						state: {
							type: "FAILED",
							name: "Failed",
							id: "new-state-id",
							timestamp: new Date().toISOString(),
							message: "State changed successfully",
						},
					});
				}),
			],
		},
	},
};

export const Failed: Story = {
	args: {
		currentState: baseState,
		open: true,
		onOpenChange: () => {},
		title: "Change Task Run State",
		onSubmitChange: () => {
			const error = new Error("Something went wrong changing the state");
			toast.error(error.message);
			return Promise.reject(error);
		},
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/task_runs/:id/set_state"), () => {
					return new HttpResponse(
						JSON.stringify({
							detail: "Something went wrong changing the state",
						}),
						{ status: 400 },
					);
				}),
			],
		},
	},
};
