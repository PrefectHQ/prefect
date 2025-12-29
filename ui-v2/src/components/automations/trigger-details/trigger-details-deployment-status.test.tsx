import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TriggerDetailsDeploymentStatus } from "./trigger-details-deployment-status";

describe("TriggerDetailsDeploymentStatus", () => {
	describe("any deployment (empty deploymentIds)", () => {
		it("renders 'any deployment' when deploymentIds is empty", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(screen.getByText("When")).toBeInTheDocument();
			expect(screen.getByText("any deployment")).toBeInTheDocument();
		});

		it("renders reactive posture as 'enters'", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(screen.getByText("enters")).toBeInTheDocument();
		});

		it("renders proactive posture as 'stays in'", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
					time={30}
				/>,
			);
			expect(screen.getByText("stays in")).toBeInTheDocument();
		});
	});

	describe("status display", () => {
		it("renders 'ready' status in lowercase", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(screen.getByText("ready")).toBeInTheDocument();
		});

		it("renders 'not_ready' status as 'not ready'", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="not_ready"
				/>,
			);
			expect(screen.getByText("not ready")).toBeInTheDocument();
		});
	});

	describe("time duration for proactive posture", () => {
		it("shows time duration for proactive posture", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
					time={30}
				/>,
			);
			expect(screen.getByText("for 30 seconds")).toBeInTheDocument();
		});

		it("shows longer time duration correctly", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
					time={3600}
				/>,
			);
			expect(screen.getByText("for 1 hour")).toBeInTheDocument();
		});

		it("does not show time for reactive posture", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="ready"
					time={30}
				/>,
			);
			expect(screen.queryByText(/for \d+/)).not.toBeInTheDocument();
		});

		it("does not show time when time is 0", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
					time={0}
				/>,
			);
			expect(screen.queryByText(/for \d+/)).not.toBeInTheDocument();
		});

		it("does not show time when time is undefined", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
				/>,
			);
			expect(screen.queryByText(/for \d+/)).not.toBeInTheDocument();
		});
	});

	describe("specific deployments", () => {
		it("renders singular 'deployment' for single deployment", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={["my-deployment"]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(screen.getByText("deployment")).toBeInTheDocument();
			expect(screen.queryByText("deployments")).not.toBeInTheDocument();
		});

		it("renders plural 'deployments' for multiple deployments", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={["my-app", "other-app"]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(screen.getByText("deployments")).toBeInTheDocument();
		});

		it("renders deployment link placeholders", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={["my-app"]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(
				screen.getByTestId("deployment-link-placeholder"),
			).toBeInTheDocument();
			expect(screen.getByText("Deployment-my-app")).toBeInTheDocument();
		});

		it("renders 'or' between two deployments", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={["my-app", "other-app"]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(screen.getByText("or")).toBeInTheDocument();
			expect(screen.getByText("Deployment-my-app")).toBeInTheDocument();
			expect(screen.getByText("Deployment-other-app")).toBeInTheDocument();
		});

		it("renders 'or' only before the last deployment for three deployments", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={["app-one", "app-two", "app-three"]}
					posture="Reactive"
					status="ready"
				/>,
			);
			const orElements = screen.getAllByText("or");
			expect(orElements).toHaveLength(1);
			expect(screen.getByText("Deployment-app-one")).toBeInTheDocument();
			expect(screen.getByText("Deployment-app-two")).toBeInTheDocument();
			expect(screen.getByText("Deployment-app-three")).toBeInTheDocument();
		});
	});

	describe("complete output scenarios", () => {
		it("renders 'When any deployment enters ready'", () => {
			const { container } = render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(container.textContent).toContain("When");
			expect(container.textContent).toContain("any deployment");
			expect(container.textContent).toContain("enters");
			expect(container.textContent).toContain("ready");
		});

		it("renders 'When any deployment stays in not ready for 30 seconds'", () => {
			const { container } = render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
					time={30}
				/>,
			);
			expect(container.textContent).toContain("When");
			expect(container.textContent).toContain("any deployment");
			expect(container.textContent).toContain("stays in");
			expect(container.textContent).toContain("not ready");
			expect(container.textContent).toContain("for 30 seconds");
		});

		it("renders deployment with proactive posture and time", () => {
			const { container } = render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={["my-app", "other-app"]}
					posture="Proactive"
					status="not_ready"
					time={30}
				/>,
			);
			expect(container.textContent).toContain("When");
			expect(container.textContent).toContain("deployments");
			expect(container.textContent).toContain("Deployment-my-app");
			expect(container.textContent).toContain("or");
			expect(container.textContent).toContain("Deployment-other-app");
			expect(container.textContent).toContain("stays in");
			expect(container.textContent).toContain("not ready");
			expect(container.textContent).toContain("for 30 seconds");
		});
	});
});
