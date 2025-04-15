import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { SortFilters } from "./sort-filter.constants";

type SortFilterProps = {
	defaultValue?: SortFilters;
	onSelect: (filter: SortFilters) => void;
	value: undefined | SortFilters;
};

export const SortFilter = ({
	defaultValue,
	value,
	onSelect,
}: SortFilterProps) => {
	return (
		<Select defaultValue={defaultValue} value={value} onValueChange={onSelect}>
			<SelectTrigger aria-label="Flow run sort order">
				<SelectValue placeholder="Sort by" />
			</SelectTrigger>
			<SelectContent>
				<SelectItem value="START_TIME_DESC">Newest to oldest</SelectItem>
				<SelectItem value="START_TIME_ASC">Oldest to newest</SelectItem>
				<SelectItem value="NAME_ASC">A to Z</SelectItem>
				<SelectItem value="NAME_DESC">Z to A</SelectItem>
			</SelectContent>
		</Select>
	);
};
