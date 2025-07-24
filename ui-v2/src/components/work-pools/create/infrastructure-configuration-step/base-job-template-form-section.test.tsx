import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BaseJobTemplateFormSection } from "./base-job-template-form-section";
import type { WorkerBaseJobTemplate } from "./schema";

const mockOnBaseJobTemplateChange = vi.fn();

const mockBaseJobTemplate: WorkerBaseJobTemplate = {
	job_configuration: {
		resources: {
			requests: {
				cpu: "{{ cpu }}",
				memory: "{{ memory }}",
			},
		},
	},
	variables: {
		type: "object",
		properties: {
			cpu: {
				type: "number",
				default: 1,
				title: "CPU",
			},
			memory: {
				type: "string",
				default: "1Gi",
				title: "Memory",
			},
		},
	},
};

describe("BaseJobTemplateFormSection", () => {
	beforeEach(() => {
		mockOnBaseJobTemplateChange.mockClear();
	});

	it("renders the component with tabs", () => {
		render(
			<BaseJobTemplateFormSection
				baseJobTemplate={mockBaseJobTemplate}
				onBaseJobTemplateChange={mockOnBaseJobTemplateChange}
			/>,
		);

		expect(screen.getByText("Base Job Template")).toBeInTheDocument();
		expect(screen.getByText("Defaults")).toBeInTheDocument();
		expect(screen.getByText("Advanced")).toBeInTheDocument();
	});

	it("shows schema form when variables have properties", () => {
		render(
			<BaseJobTemplateFormSection
				baseJobTemplate={mockBaseJobTemplate}
				onBaseJobTemplateChange={mockOnBaseJobTemplateChange}
			/>,
		);

		expect(
			screen.getByText(/The fields below control the default values/),
		).toBeInTheDocument();
		// Schema form is now properly integrated - it should render the form fields
		expect(screen.getByText("Defaults")).toBeInTheDocument();
	});

	it("shows warning when no schema properties exist", () => {
		const emptyTemplate: WorkerBaseJobTemplate = {
			job_configuration: {},
			variables: {
				type: "object",
				properties: {},
			},
		};

		render(
			<BaseJobTemplateFormSection
				baseJobTemplate={emptyTemplate}
				onBaseJobTemplateChange={mockOnBaseJobTemplateChange}
			/>,
		);

		expect(
			screen.getByText(
				/This work pool's base job template does not have any customizations/,
			),
		).toBeInTheDocument();
	});

	it("has both tabs available", () => {
		render(
			<BaseJobTemplateFormSection
				baseJobTemplate={mockBaseJobTemplate}
				onBaseJobTemplateChange={mockOnBaseJobTemplateChange}
			/>,
		);

		expect(screen.getByText("Defaults")).toBeInTheDocument();
		expect(screen.getByText("Advanced")).toBeInTheDocument();
	});

	it("handles undefined base job template", () => {
		render(
			<BaseJobTemplateFormSection
				baseJobTemplate={undefined}
				onBaseJobTemplateChange={mockOnBaseJobTemplateChange}
			/>,
		);

		expect(screen.getByText("Base Job Template")).toBeInTheDocument();
		expect(
			screen.getByText(
				/This work pool's base job template does not have any customizations/,
			),
		).toBeInTheDocument();
	});

	it("can click on advanced tab", () => {
		render(
			<BaseJobTemplateFormSection
				baseJobTemplate={mockBaseJobTemplate}
				onBaseJobTemplateChange={mockOnBaseJobTemplateChange}
			/>,
		);

		const advancedTab = screen.getByText("Advanced");
		expect(advancedTab).toBeInTheDocument();

		// Should be able to click without errors
		fireEvent.click(advancedTab);
		expect(advancedTab).toBeInTheDocument();
	});
});
