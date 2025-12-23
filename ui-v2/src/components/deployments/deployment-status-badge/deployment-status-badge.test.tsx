import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DeploymentStatusBadge } from "./deployment-status-badge";

describe("DeploymentStatusBadge", () => {
	it("renders ready status with correct label and styling", () => {
		render(
			<DeploymentStatusBadge deployment={{ status: "READY", paused: false }} />,
		);

		expect(screen.getByText("Ready")).toBeInTheDocument();
		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("bg-secondary", "text-secondary-foreground");
	});

	it("renders not_ready status with correct label and styling", () => {
		render(
			<DeploymentStatusBadge
				deployment={{ status: "NOT_READY", paused: false }}
			/>,
		);

		expect(screen.getByText("Not Ready")).toBeInTheDocument();
		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("bg-secondary", "text-secondary-foreground");
	});

	it("renders disabled status when paused is true", () => {
		render(
			<DeploymentStatusBadge deployment={{ status: "READY", paused: true }} />,
		);

		expect(screen.getByText("Disabled")).toBeInTheDocument();
		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("bg-secondary", "text-secondary-foreground");
	});

	it("shows disabled status regardless of underlying status when paused", () => {
		render(
			<DeploymentStatusBadge
				deployment={{ status: "NOT_READY", paused: true }}
			/>,
		);

		expect(screen.getByText("Disabled")).toBeInTheDocument();
		expect(screen.queryByText("Not Ready")).not.toBeInTheDocument();
	});

	it("includes status circle for ready status", () => {
		render(
			<DeploymentStatusBadge deployment={{ status: "READY", paused: false }} />,
		);

		const circle = document.querySelector("svg.h-2.w-2");
		expect(circle).toBeInTheDocument();
		expect(circle).toHaveClass("bg-green-500");
	});

	it("includes status circle for not_ready status", () => {
		render(
			<DeploymentStatusBadge
				deployment={{ status: "NOT_READY", paused: false }}
			/>,
		);

		const circle = document.querySelector("svg.h-2.w-2");
		expect(circle).toBeInTheDocument();
		expect(circle).toHaveClass("bg-red-500");
	});

	it("includes pause icon for disabled status", () => {
		render(
			<DeploymentStatusBadge deployment={{ status: "READY", paused: true }} />,
		);

		const pauseIcon = document.querySelector("svg.h-2.w-2");
		expect(pauseIcon).toBeInTheDocument();
		expect(pauseIcon).toHaveClass("text-muted-foreground");
	});

	it("applies custom className", () => {
		render(
			<DeploymentStatusBadge
				deployment={{ status: "READY", paused: false }}
				className="custom-class"
			/>,
		);

		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("custom-class");
	});

	it("handles null status by defaulting to NOT_READY", () => {
		render(
			<DeploymentStatusBadge deployment={{ status: null, paused: false }} />,
		);

		expect(screen.getByText("Not Ready")).toBeInTheDocument();
	});
});
