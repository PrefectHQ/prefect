import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockInMemoryLocalStorage } from "@tests/utils/browser";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PinDeploymentButton } from "./pin-deployment-button";
import { PINNED_DEPLOYMENTS_STORAGE_KEY } from "./use-pinned-deployments";

describe("PinDeploymentButton", () => {
	let restoreLocalStorage: () => void;

	beforeEach(() => {
		restoreLocalStorage = mockInMemoryLocalStorage();
	});

	afterEach(() => {
		restoreLocalStorage();
	});

	it("pins an unpinned deployment", async () => {
		const user = userEvent.setup();
		render(<PinDeploymentButton deploymentId="deployment-1" />);

		const button = screen.getByRole("button", { name: "Pin deployment" });
		expect(button).toHaveAttribute("aria-pressed", "false");

		await user.click(button);

		expect(
			screen.getByRole("button", { name: "Unpin deployment" }),
		).toHaveAttribute("aria-pressed", "true");
		expect(localStorage.getItem(PINNED_DEPLOYMENTS_STORAGE_KEY)).toBe(
			JSON.stringify(["deployment-1"]),
		);
	});

	it("unpins a pinned deployment", async () => {
		localStorage.setItem(
			PINNED_DEPLOYMENTS_STORAGE_KEY,
			JSON.stringify(["deployment-1", "deployment-2"]),
		);
		const user = userEvent.setup();
		render(<PinDeploymentButton deploymentId="deployment-1" />);

		await user.click(screen.getByRole("button", { name: "Unpin deployment" }));

		expect(
			screen.getByRole("button", { name: "Pin deployment" }),
		).toBeInTheDocument();
		expect(localStorage.getItem(PINNED_DEPLOYMENTS_STORAGE_KEY)).toBe(
			JSON.stringify(["deployment-2"]),
		);
	});

	it("does not trigger click handlers on its container", async () => {
		const onContainerClick = vi.fn();
		const user = userEvent.setup();
		render(
			// biome-ignore lint/a11y/noStaticElementInteractions: stands in for a clickable table row
			// biome-ignore lint/a11y/useKeyWithClickEvents: stands in for a clickable table row
			<div onClick={onContainerClick}>
				<PinDeploymentButton deploymentId="deployment-1" />
			</div>,
		);

		await user.click(screen.getByRole("button", { name: "Pin deployment" }));

		expect(onContainerClick).not.toHaveBeenCalled();
	});
});
