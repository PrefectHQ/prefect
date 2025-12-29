import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TriggerDetailsCustom } from "./trigger-details-custom";

describe("TriggerDetailsCustom", () => {
	it("renders the custom trigger text", () => {
		render(<TriggerDetailsCustom />);
		expect(screen.getByText("A custom trigger")).toBeInTheDocument();
	});
});
