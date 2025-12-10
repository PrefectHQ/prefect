import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import {
	DateRangeFilter,
	type DateRangeUrlState,
	dateRangeValueToUrlState,
	urlStateToDateRangeValue,
} from "@/components/flow-runs/flow-runs-list";
import type { DateRangeSelectValue } from "@/components/ui/date-range-select";

describe("Date Range Filter", () => {
	describe("urlStateToDateRangeValue", () => {
		it("should return null for empty state", () => {
			const result = urlStateToDateRangeValue({});
			expect(result).toBeNull();
		});

		it("should convert past-hour preset to span value", () => {
			const result = urlStateToDateRangeValue({ range: "past-hour" });
			expect(result).toEqual({ type: "span", seconds: -3600 });
		});

		it("should convert past-24-hours preset to span value", () => {
			const result = urlStateToDateRangeValue({ range: "past-24-hours" });
			expect(result).toEqual({ type: "span", seconds: -86400 });
		});

		it("should convert past-7-days preset to span value", () => {
			const result = urlStateToDateRangeValue({ range: "past-7-days" });
			expect(result).toEqual({ type: "span", seconds: -604800 });
		});

		it("should convert past-30-days preset to span value", () => {
			const result = urlStateToDateRangeValue({ range: "past-30-days" });
			expect(result).toEqual({ type: "span", seconds: -2592000 });
		});

		it("should convert today preset to period value", () => {
			const result = urlStateToDateRangeValue({ range: "today" });
			expect(result).toEqual({ type: "period", period: "Today" });
		});

		it("should convert custom start/end dates to range value", () => {
			const start = "2024-01-01T00:00:00.000Z";
			const end = "2024-01-07T00:00:00.000Z";
			const result = urlStateToDateRangeValue({ start, end });
			expect(result).toEqual({
				type: "range",
				startDate: new Date(start),
				endDate: new Date(end),
			});
		});

		it("should prioritize custom dates over preset range", () => {
			const start = "2024-01-01T00:00:00.000Z";
			const end = "2024-01-07T00:00:00.000Z";
			const result = urlStateToDateRangeValue({
				range: "past-7-days",
				start,
				end,
			});
			expect(result).toEqual({
				type: "range",
				startDate: new Date(start),
				endDate: new Date(end),
			});
		});
	});

	describe("dateRangeValueToUrlState", () => {
		it("should return empty object for null value", () => {
			const result = dateRangeValueToUrlState(null);
			expect(result).toEqual({});
		});

		it("should convert past-hour span to preset", () => {
			const value: DateRangeSelectValue = { type: "span", seconds: -3600 };
			const result = dateRangeValueToUrlState(value);
			expect(result).toEqual({ range: "past-hour" });
		});

		it("should convert past-24-hours span to preset", () => {
			const value: DateRangeSelectValue = { type: "span", seconds: -86400 };
			const result = dateRangeValueToUrlState(value);
			expect(result).toEqual({ range: "past-24-hours" });
		});

		it("should convert past-7-days span to preset", () => {
			const value: DateRangeSelectValue = { type: "span", seconds: -604800 };
			const result = dateRangeValueToUrlState(value);
			expect(result).toEqual({ range: "past-7-days" });
		});

		it("should convert past-30-days span to preset", () => {
			const value: DateRangeSelectValue = { type: "span", seconds: -2592000 };
			const result = dateRangeValueToUrlState(value);
			expect(result).toEqual({ range: "past-30-days" });
		});

		it("should convert Today period to preset", () => {
			const value: DateRangeSelectValue = { type: "period", period: "Today" };
			const result = dateRangeValueToUrlState(value);
			expect(result).toEqual({ range: "today" });
		});

		it("should convert range to start/end dates", () => {
			const startDate = new Date("2024-01-01T00:00:00.000Z");
			const endDate = new Date("2024-01-07T00:00:00.000Z");
			const value: DateRangeSelectValue = {
				type: "range",
				startDate,
				endDate,
			};
			const result = dateRangeValueToUrlState(value);
			expect(result).toEqual({
				start: startDate.toISOString(),
				end: endDate.toISOString(),
			});
		});

		it("should convert around value to start/end dates", () => {
			const date = new Date("2024-01-15T12:00:00.000Z");
			const value: DateRangeSelectValue = {
				type: "around",
				date,
				quantity: 1,
				unit: "day",
			};
			const result = dateRangeValueToUrlState(value);
			expect(result.start).toBeDefined();
			expect(result.end).toBeDefined();
			// The start should be 1 day before the date
			if (result.start && result.end) {
				expect(new Date(result.start).getTime()).toBe(
					date.getTime() - 86400 * 1000,
				);
				// The end should be 1 day after the date
				expect(new Date(result.end).getTime()).toBe(
					date.getTime() + 86400 * 1000,
				);
			}
		});

		it("should convert non-standard span to start/end dates", () => {
			const value: DateRangeSelectValue = {
				type: "span",
				seconds: -7200,
			}; // 2 hours
			const result = dateRangeValueToUrlState(value);
			expect(result.start).toBeDefined();
			expect(result.end).toBeDefined();
		});
	});

	describe("DateRangeFilter component", () => {
		it("should render with placeholder when no value is set", () => {
			const onValueChange = vi.fn();
			render(<DateRangeFilter value={{}} onValueChange={onValueChange} />, {
				wrapper: createWrapper(),
			});
			expect(screen.getByText("All time")).toBeVisible();
		});

		it("should call onValueChange when a preset is selected", async () => {
			const user = userEvent.setup();
			const onValueChange = vi.fn();
			render(<DateRangeFilter value={{}} onValueChange={onValueChange} />, {
				wrapper: createWrapper(),
			});

			// Click to open the dropdown
			await user.click(screen.getByText("All time"));

			// Select "Past hour" option
			await user.click(screen.getByText("Past hour"));

			expect(onValueChange).toHaveBeenCalledWith({ range: "past-hour" });
		});
	});

	describe("URL state synchronization", () => {
		it("should round-trip preset values correctly", () => {
			const presets: DateRangeUrlState[] = [
				{ range: "past-hour" },
				{ range: "past-24-hours" },
				{ range: "past-7-days" },
				{ range: "past-30-days" },
				{ range: "today" },
			];

			for (const preset of presets) {
				const dateRangeValue = urlStateToDateRangeValue(preset);
				const roundTripped = dateRangeValueToUrlState(dateRangeValue);
				expect(roundTripped).toEqual(preset);
			}
		});

		it("should round-trip custom date range correctly", () => {
			const start = "2024-01-01T00:00:00.000Z";
			const end = "2024-01-07T00:00:00.000Z";
			const urlState: DateRangeUrlState = { start, end };

			const dateRangeValue = urlStateToDateRangeValue(urlState);
			const roundTripped = dateRangeValueToUrlState(dateRangeValue);

			expect(roundTripped).toEqual(urlState);
		});
	});
});
