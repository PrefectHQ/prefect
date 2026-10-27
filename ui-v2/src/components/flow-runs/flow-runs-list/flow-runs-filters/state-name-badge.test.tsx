import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StateNameBadge } from "./state-name-badge";

describe("StateNameBadge", () => {
	it.each([
		["Failed", "bg-state-failed-100"],
		["Cached", "bg-state-completed-100"],
	])("renders %s with its built-in state type", (name, color) => {
		render(<StateNameBadge name={name} />);
		expect(screen.getByText(name)).toHaveClass(color);
	});

	it.each(["Baseline, NOT Met", "cached", "constructor"])(
		"preserves the exact custom name %s with neutral styling",
		(name) => {
			render(<StateNameBadge name={name} />);
			expect(screen.getByText(name)).toHaveClass("bg-secondary");
		},
	);
});
