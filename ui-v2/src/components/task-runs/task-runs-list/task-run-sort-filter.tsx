import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { TaskRunSortFilters } from "./task-run-sort-filter.constants";

type TaskRunsSortFilterProps = {
	defaultValue?: TaskRunSortFilters;
	onSelect: (filter: TaskRunSortFilters) => void;
	value: undefined | TaskRunSortFilters;
};

export const TaskRunsSortFilter = ({
	defaultValue,
	value,
	onSelect,
}: TaskRunsSortFilterProps) => {
	return (
		<Select
			defaultValue={defaultValue}
			value={value}
			onValueChange={(value) => {
				if (
					value === "EXPECTED_START_TIME_ASC" ||
					value === "EXPECTED_START_TIME_DESC" ||
					value === "DURATION_DESC" ||
					value === "DURATION_ASC"
				)
					onSelect(value);
			}}
		>
			<SelectTrigger aria-label="Task run sort order" className="w-full">
				<SelectValue placeholder="Sort by" />
			</SelectTrigger>
			<SelectContent>
				<SelectItem value="EXPECTED_START_TIME_DESC">
					Newest to oldest
				</SelectItem>
				<SelectItem value="EXPECTED_START_TIME_ASC">
					Oldest to newest
				</SelectItem>
				<SelectItem value="DURATION_DESC">Longest to shortest</SelectItem>
				<SelectItem value="DURATION_ASC">Shortest to longest</SelectItem>
			</SelectContent>
		</Select>
	);
};
