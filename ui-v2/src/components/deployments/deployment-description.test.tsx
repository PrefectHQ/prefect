import { render, screen, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { createFakeDeployment } from "@/mocks";
import { DeploymentDescription } from "./deployment-description";

describe("DeploymentDescription", () => {
	it("renders markdown when deployment has a description", async () => {
		const deployment = createFakeDeployment({
			description: "# Hello World",
			entrypoint: "my_flow.py:my_flow",
		});

		render(<DeploymentDescription deployment={deployment} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Hello World")).toBeInTheDocument();
		});
	});

	it("renders empty state when deployment has no description", () => {
		const deployment = createFakeDeployment({
			description: null,
			entrypoint: "my_flow.py:my_flow",
		});

		render(<DeploymentDescription deployment={deployment} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Add deployment description")).toBeInTheDocument();
		expect(
			screen.getByText(
				"You can do so by adding a description as part of your deployment configuration.",
			),
		).toBeInTheDocument();
		expect(screen.getByText("View Docs")).toBeInTheDocument();
	});

	it("renders empty state when deployment has an empty string description", () => {
		const deployment = createFakeDeployment({
			description: "",
			entrypoint: "my_flow.py:my_flow",
		});

		render(<DeploymentDescription deployment={deployment} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Add deployment description")).toBeInTheDocument();
	});

	it("renders deprecated message when deployment has null entrypoint", () => {
		const deployment = createFakeDeployment({
			entrypoint: null,
			description: "Some description",
		});

		render(<DeploymentDescription deployment={deployment} />, {
			wrapper: createWrapper(),
		});

		expect(
			screen.getByText("This deployment is deprecated"),
		).toBeInTheDocument();
		expect(
			screen.getByText(
				"With the General Availability release of Prefect 2, we modified the approach to creating deployments.",
			),
		).toBeInTheDocument();
		expect(screen.getByText("View Docs")).toBeInTheDocument();
	});

	it("renders deprecated message when deployment has empty string entrypoint", () => {
		const deployment = createFakeDeployment({
			entrypoint: "",
		});

		render(<DeploymentDescription deployment={deployment} />, {
			wrapper: createWrapper(),
		});

		expect(
			screen.getByText("This deployment is deprecated"),
		).toBeInTheDocument();
	});

	it("prioritizes deprecated message over empty description", () => {
		const deployment = createFakeDeployment({
			entrypoint: null,
			description: null,
		});

		render(<DeploymentDescription deployment={deployment} />, {
			wrapper: createWrapper(),
		});

		expect(
			screen.getByText("This deployment is deprecated"),
		).toBeInTheDocument();
		expect(
			screen.queryByText("Add deployment description"),
		).not.toBeInTheDocument();
	});
});
