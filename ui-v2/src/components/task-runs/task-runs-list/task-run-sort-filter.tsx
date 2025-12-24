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
		<Select defaultValue={defaultValue} value={value} onValueChange={onSelect}>
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
			</SelectContent>
		</Select>
	);
};
