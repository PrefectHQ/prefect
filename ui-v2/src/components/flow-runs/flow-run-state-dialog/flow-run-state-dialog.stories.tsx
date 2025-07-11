import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { toast } from "sonner";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import type { RunStateFormValues } from "@/components/ui/run-state-change-dialog";
import { RunStateChangeDialog } from "@/components/ui/run-state-change-dialog";
import { StateBadge } from "@/components/ui/state-badge";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";

const meta = {
	title: "Components/FlowRuns/RunStateChangeDialog",
	component: RunStateChangeDialog,
	decorators: [reactQueryDecorator, toastDecorator],
} satisfies Meta<typeof RunStateChangeDialog>;

export default meta;
type Story = StoryObj<typeof RunStateChangeDialog>;

const DialogDemo = () => {
	const [open, setOpen] = useState(false);

	return (
		<div className="flex flex-col gap-4">
			<Button onClick={() => setOpen(true)}>Change Flow Run State</Button>
			<RunStateChangeDialog
				currentState={{
					type: "COMPLETED",
					name: "Completed",
				}}
				open={open}
				onOpenChange={setOpen}
				title="Change Flow Run State"
				onSubmitChange={async (values: RunStateFormValues) => {
					await new Promise((resolve) => setTimeout(resolve, 500));
					toast.success(
						<div className="flex items-center gap-2">
							Flow run state changed to{" "}
							<StateBadge
								type={values.state as components["schemas"]["StateType"]}
								name={values.state}
							/>
						</div>,
					);
				}}
			/>
		</div>
	);
};

export const Default: Story = {
	render: () => <DialogDemo />,
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
