import type { Meta, StoryObj } from "@storybook/react";

import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Form } from "@/components/ui/form";
import { createFakeAutomation } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { zodResolver } from "@hookform/resolvers/zod";
import { fn } from "@storybook/test";
import { buildApiUrl } from "@tests/utils/handlers";
import { http, HttpResponse } from "msw";
import { useForm } from "react-hook-form";
import { ActionsStep } from "./actions-step";

const MOCK_AUTOMATIONS_DATA = Array.from({ length: 5 }, createFakeAutomation);

const meta = {
	title: "Components/Automations/Wizard/ActionsStep",
	component: ActionsStepsStory,
	args: { onPrevious: fn(), onNext: fn() },
	decorators: [reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/automations/filter"), () => {
					return HttpResponse.json(MOCK_AUTOMATIONS_DATA);
				}),
			],
		},
	},
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "ActionsStep" };

function ActionsStepsStory() {
	const form = useForm<AutomationWizardSchema>({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: { actions: [{ type: undefined }] },
	});

	return (
		<Form {...form}>
			<form>
				<ActionsStep />
			</form>
		</Form>
	);
}
