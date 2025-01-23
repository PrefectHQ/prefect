import { Automation } from "@/api/automations";
import { routerDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { ActionDetails } from "./action-details";

const ACTIONS: Array<Automation["actions"][number]> = [
	{ type: "do-nothing" },
	{ type: "cancel-flow-run" },
	{ type: "suspend-flow-run" },
	{ type: "cancel-flow-run" },
	{ type: "resume-flow-run" },
	{ type: "run-deployment", deployment_id: null, source: "inferred" },
	{
		type: "run-deployment",
		deployment_id: "abc",
		source: "selected",
		// @ts-expect-error Need to fix typings with open API
		parameters: { Hello: "World", Goodbye: "World" },
		// @ts-expect-error Need to fix typings with open API
		job_variables: { var1: "abc", var2: { foo: "bar" } },
	},
	{ type: "pause-deployment", deployment_id: null, source: "inferred" },
	{ type: "pause-deployment", deployment_id: "abc", source: "selected" },
	{ type: "resume-deployment", deployment_id: null, source: "inferred" },
	{ type: "resume-deployment", deployment_id: "abc", source: "selected" },
	{ type: "pause-work-queue", work_queue_id: null, source: "inferred" },
	{ type: "pause-work-queue", work_queue_id: "abc", source: "selected" },
	{ type: "resume-work-queue", work_queue_id: null, source: "inferred" },
	{ type: "resume-work-queue", work_queue_id: "abc", source: "selected" },
	{ type: "pause-work-pool", work_pool_id: null, source: "inferred" },
	{ type: "pause-work-pool", work_pool_id: "abc", source: "selected" },
	{ type: "resume-work-pool", work_pool_id: null, source: "inferred" },
	{ type: "resume-work-pool", work_pool_id: "abc", source: "selected" },
	{ type: "pause-automation", automation_id: null, source: "inferred" },
	{ type: "pause-automation", automation_id: "abc", source: "selected" },
	{ type: "resume-automation", automation_id: null, source: "inferred" },
	{ type: "resume-automation", automation_id: "abc", source: "selected" },
	{
		type: "change-flow-run-state",
		state: "CANCELLED",
	},
	{
		type: "change-flow-run-state",
		state: "CANCELLING",
	},
	{
		type: "change-flow-run-state",
		state: "COMPLETED",
	},
	{
		type: "change-flow-run-state",
		state: "CRASHED",
	},
	{
		type: "change-flow-run-state",
		state: "FAILED",
	},
	{
		type: "change-flow-run-state",
		state: "PAUSED",
	},
	{
		type: "change-flow-run-state",
		state: "PENDING",
	},
	{
		type: "change-flow-run-state",
		state: "RUNNING",
		message: "My message",
		name: "My name",
	},
	{
		type: "change-flow-run-state",
		state: "SCHEDULED",
	},
	{
		type: "send-notification",
		block_document_id: "abc",
		body: "my_body",
		subject: "my_subject",
	},
	{
		type: "call-webhook",
		block_document_id: "abc",
		payload: "my_payload",
	},
];

const meta = {
	title: "Components/Automations/ActionDetails",
	component: ActionDetailsStory,
	decorators: [routerDecorator],
} satisfies Meta<typeof ActionDetails>;

export default meta;

export const Story: StoryObj = {
	name: "ActionDetails",
};

function ActionDetailsStory() {
	return (
		<ul className="flex flex-col gap-4">
			{ACTIONS.map((action, i) => (
				<li key={i}>
					<ActionDetails key={i} action={action} />
				</li>
			))}
		</ul>
	);
}
