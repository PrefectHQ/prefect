import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { createFakeDeployment } from "@/mocks";
import { DeploymentParametersTable } from "./deployment-parameters-table";

const MOCK_DEPLOYMENT = createFakeDeployment({
	parameter_openapi_schema: {
		title: "Parameters",
		type: "object",
		properties: {
			name: {
				default: "world",
				position: 0,
				title: "name",
				type: "string",
			},
			goodbye: {
				default: false,
				position: 1,
				title: "goodbye",
				type: "boolean",
			},
		},
	},
	parameters: {
		goodbye: false,
		name: "world",
	},
});

describe("DeploymentParametersTable", () => {
	it("renders table with rows", () => {
		// ------------ Setup
		render(<DeploymentParametersTable deployment={MOCK_DEPLOYMENT} />);

		// ------------ Assert
		expect(screen.getByRole("cell", { name: /name/i })).toBeVisible();
		expect(screen.getByRole("cell", { name: /goodbye/i })).toBeVisible();
	});

	it("filters table rows", async () => {
		// ------------ Setup
		const user = userEvent.setup();

		render(<DeploymentParametersTable deployment={MOCK_DEPLOYMENT} />);

		// ------------ Act
		await user.type(screen.getByRole("textbox"), "name");

		// ------------ Assert
		await waitFor(() =>
			expect(
				screen.queryByRole("cell", { name: /goodbye/i }),
			).not.toBeInTheDocument(),
		);
		expect(screen.getByRole("cell", { name: /name/i })).toBeVisible();
	});

	it("filters no results", async () => {
		// ------------ Setup
		const user = userEvent.setup();

		render(<DeploymentParametersTable deployment={MOCK_DEPLOYMENT} />);

		// ------------ Act
		await user.type(screen.getByRole("textbox"), "no results found");

		// ------------ Assert
		await waitFor(() =>
			expect(
				screen.queryByRole("cell", { name: /goodbye/i }),
			).not.toBeInTheDocument(),
		);
		expect(
			screen.queryByRole("cell", { name: /name/i }),
		).not.toBeInTheDocument();

		expect(screen.getByText("No results.")).toBeVisible();
	});

	it("renders empty table when parameter_openapi_schema has no properties", () => {
		// ------------ Setup
		const deployment = createFakeDeployment({
			parameter_openapi_schema: { title: "Parameters", type: "object" },
			parameters: {},
		});

		// ------------ Act
		render(<DeploymentParametersTable deployment={deployment} />);

		// ------------ Assert
		expect(screen.getByText("No results.")).toBeVisible();
	});

	it("renders empty table when parameter_openapi_schema.properties is null", () => {
		// ------------ Setup
		const deployment = createFakeDeployment({
			parameter_openapi_schema: { properties: null },
			parameters: {},
		});

		// ------------ Act
		render(<DeploymentParametersTable deployment={deployment} />);

		// ------------ Assert
		expect(screen.getByText("No results.")).toBeVisible();
	});

	it("renders empty table when parameter_openapi_schema is missing", () => {
		// ------------ Setup
		const deployment = createFakeDeployment({
			parameter_openapi_schema: undefined,
			parameters: {},
		});

		// ------------ Act
		render(<DeploymentParametersTable deployment={deployment} />);

		// ------------ Assert
		expect(screen.getByText("No results.")).toBeVisible();
	});

	it("renders rows when parameters is missing but properties exist", () => {
		// ------------ Setup
		const deployment = createFakeDeployment({
			parameter_openapi_schema: {
				title: "Parameters",
				type: "object",
				properties: {
					name: {
						default: "world",
						position: 0,
						title: "name",
						type: "string",
					},
				},
			},
			parameters: undefined,
		});

		// ------------ Act
		render(<DeploymentParametersTable deployment={deployment} />);

		// ------------ Assert
		expect(screen.getByRole("cell", { name: /name/i })).toBeVisible();
	});
});
