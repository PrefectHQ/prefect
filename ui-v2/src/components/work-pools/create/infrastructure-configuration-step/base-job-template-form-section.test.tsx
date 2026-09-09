import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "@/mocks/mock-json-input";
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

	it("writes free-form object defaults to the template as plain objects", async () => {
		const templateWithEnv: WorkerBaseJobTemplate = {
			job_configuration: { env: "{{ env }}" },
			variables: {
				type: "object",
				properties: {
					env: {
						type: "object",
						title: "Environment Variables",
						additionalProperties: { type: "string" },
						default: {},
					},
				},
			},
		};

		render(
			<BaseJobTemplateFormSection
				baseJobTemplate={templateWithEnv}
				onBaseJobTemplateChange={mockOnBaseJobTemplateChange}
			/>,
		);

		const jsonInput = await screen.findByTestId("mock-json-input");
		fireEvent.change(jsonInput, {
			target: { value: '{"CDWH_ENVIRONMENT": "dev"}' },
		});

		await waitFor(() => {
			const lastCall = mockOnBaseJobTemplateChange.mock.lastCall as
				| [WorkerBaseJobTemplate]
				| undefined;
			expect(lastCall?.[0].variables?.properties?.env).toMatchObject({
				default: { CDWH_ENVIRONMENT: "dev" },
			});
		});

		for (const [template] of mockOnBaseJobTemplateChange.mock.calls as [
			WorkerBaseJobTemplate,
		][]) {
			expect(JSON.stringify(template.variables?.properties?.env)).not.toContain(
				"__prefect_kind",
			);
		}
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
