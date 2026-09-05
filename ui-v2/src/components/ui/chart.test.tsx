import { render, screen } from "@testing-library/react";
import type { TooltipPayload } from "recharts";
import { describe, expect, it, vi } from "vitest";
import { ChartContainer, ChartTooltipContent } from "./chart";

describe("ChartTooltipContent", () => {
	it("passes range values and the full payload to a custom formatter", () => {
		const payload: TooltipPayload = [
			{
				color: "blue",
				dataKey: (item: { duration: number }) => item.duration,
				graphicalItemId: "duration",
				name: "Duration",
				payload: { fill: "blue" },
				value: [1, 3],
			},
		];
		const formatter = vi.fn((value: (typeof payload)[number]["value"]) => (
			<span>{Array.isArray(value) ? value.join(" to ") : value}</span>
		));

		render(
			<ChartContainer config={{ duration: { label: "Duration" } }}>
				<ChartTooltipContent active formatter={formatter} payload={payload} />
			</ChartContainer>,
		);

		expect(screen.getByText("1 to 3")).toBeVisible();
		expect(formatter).toHaveBeenCalledWith(
			payload[0].value,
			payload[0].name,
			payload[0],
			0,
			payload,
		);
	});
});
