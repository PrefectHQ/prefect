import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createFakeDeployment } from "@/mocks";
import { DeploymentMetadata } from "./deployment-metadata";

describe("DeploymentMetadata", () => {
	it("renders basic deployment metadata", () => {
		const deployment = createFakeDeployment({
			id: "deployment-123",
			flow_id: "flow-456",
			status: "READY",
		});

		render(<DeploymentMetadata deployment={deployment} />);

		expect(screen.getByText("Status")).toBeInTheDocument();
		expect(screen.getByText("Deployment ID")).toBeInTheDocument();
		expect(screen.getByText("Flow ID")).toBeInTheDocument();
	});

	it("renders code_repository_url as a link when provided", () => {
		const repoUrl = "https://github.com/PrefectHQ/prefect";
		const deployment = createFakeDeployment({
			code_repository_url: repoUrl,
		});

		render(<DeploymentMetadata deployment={deployment} />);

		expect(screen.getByText("Repository")).toBeInTheDocument();
		const link = screen.getByRole("link", { name: new RegExp(repoUrl) });
		expect(link).toHaveAttribute("href", repoUrl);
		expect(link).toHaveAttribute("target", "_blank");
		expect(link).toHaveAttribute("rel", "noopener noreferrer");
	});

	it("renders 'None' when code_repository_url is not provided", () => {
		const deployment = createFakeDeployment({
			code_repository_url: undefined,
		});

		render(<DeploymentMetadata deployment={deployment} />);

		expect(screen.getByText("Repository")).toBeInTheDocument();
		// The component should show "None" for empty repository URL
		const noneElements = screen.getAllByText("None");
		expect(noneElements.length).toBeGreaterThan(0);
	});

	it("renders tags when provided", () => {
		const deployment = createFakeDeployment({
			tags: ["production", "critical"],
		});

		render(<DeploymentMetadata deployment={deployment} />);

		expect(screen.getByText("Tags")).toBeInTheDocument();
		expect(screen.getByText("production")).toBeInTheDocument();
		expect(screen.getByText("critical")).toBeInTheDocument();
	});

	it("renders version when provided", () => {
		const deployment = createFakeDeployment({
			version: "v1.2.3",
		});

		render(<DeploymentMetadata deployment={deployment} />);

		expect(screen.getByText("Deployment Version")).toBeInTheDocument();
		expect(screen.getByText("v1.2.3")).toBeInTheDocument();
	});
});
