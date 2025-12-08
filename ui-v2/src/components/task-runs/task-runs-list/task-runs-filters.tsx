import { SearchInput } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

export const TASK_RUN_SORT_OPTIONS = [
	"EXPECTED_START_TIME_DESC",
	"EXPECTED_START_TIME_ASC",
	"NAME_ASC",
	"NAME_DESC",
] as const;

export type TaskRunSortOption = (typeof TASK_RUN_SORT_OPTIONS)[number];

const SORT_LABELS: Record<TaskRunSortOption, string> = {
	EXPECTED_START_TIME_DESC: "Newest to oldest",
	EXPECTED_START_TIME_ASC: "Oldest to newest",
	NAME_ASC: "A to Z",
	NAME_DESC: "Z to A",
};

export type TaskRunsFiltersProps = {
	search: {
		onChange: (value: string) => void;
		value: string;
	};
	sort: {
		value: TaskRunSortOption | undefined;
		onSelect: (sort: TaskRunSortOption) => void;
	};
};

export const TaskRunsFilters = ({ search, sort }: TaskRunsFiltersProps) => {
	return (
		<div className="flex items-center gap-2">
			<div className="flex items-center gap-2 pr-2 border-r-2">
				<div className="min-w-56">
					<SearchInput
						aria-label="search by task run name"
						placeholder="Search by task run name"
						value={search.value}
						onChange={(e) => search.onChange(e.target.value)}
					/>
				</div>
			</div>
			<TaskRunsSortFilter value={sort.value} onSelect={sort.onSelect} />
		</div>
	);
};

type TaskRunsSortFilterProps = {
	defaultValue?: TaskRunSortOption;
	onSelect: (filter: TaskRunSortOption) => void;
	value: undefined | TaskRunSortOption;
};

export const TaskRunsSortFilter = ({
	defaultValue,
	value,
	onSelect,
}: TaskRunsSortFilterProps) => {
	return (
		<Select defaultValue={defaultValue} value={value} onValueChange={onSelect}>
			<SelectTrigger aria-label="Task run sort order">
				<SelectValue placeholder="Sort by" />
			</SelectTrigger>
			<SelectContent>
				{TASK_RUN_SORT_OPTIONS.map((option) => (
					<SelectItem key={option} value={option}>
						{SORT_LABELS[option]}
					</SelectItem>
				))}
			</SelectContent>
		</Select>
	);
};
