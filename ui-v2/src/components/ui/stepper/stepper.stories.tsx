import type { Meta, StoryObj } from "@storybook/react";

import { Stepper } from "./stepper";
import { FormStepperStory } from "./stories/form-stepper-story";
import { StepperStory } from "./stories/stepper-story";

const meta: Meta<typeof Stepper> = {
	title: "UI/Stepper",
	component: Stepper,
};
export default meta;

export const Usage: StoryObj = {
	render: () => <StepperStory />,
};

export const FormExample: StoryObj = {
	render: () => <FormStepperStory />,
};
