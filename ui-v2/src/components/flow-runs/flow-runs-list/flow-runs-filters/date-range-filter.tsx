import { useMemo } from "react";
import {
	type DateRangeSelectValue,
	RichDateRangeSelector,
} from "@/components/ui/date-range-select";
import {
	type DateRangeUrlState,
	dateRangeValueToUrlState,
	urlStateToDateRangeValue,
} from "./date-range-url-state";

type DateRangeFilterProps = {
	value: DateRangeUrlState;
	onValueChange: (value: DateRangeUrlState) => void;
	className?: string;
};

/**
 * DateRangeFilter component for filtering flow runs by date range.
 * Wraps RichDateRangeSelector and handles URL state serialization.
 */
export const DateRangeFilter = ({
	value,
	onValueChange,
	className,
}: DateRangeFilterProps) => {
	const dateRangeValue = useMemo(
		() => urlStateToDateRangeValue(value),
		[value],
	);

	const handleValueChange = (newValue: DateRangeSelectValue) => {
		onValueChange(dateRangeValueToUrlState(newValue));
	};

	return (
		<RichDateRangeSelector
			value={dateRangeValue}
			onValueChange={handleValueChange}
			placeholder="All time"
			clearable
			className={className}
		/>
	);
};
