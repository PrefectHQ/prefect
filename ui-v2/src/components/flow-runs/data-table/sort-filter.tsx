import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

export type SortFilters =
	| "START_TIME_ASC"
	| "START_TIME_DESC"
	| "NAME_ASC"
	| "NAME_DESC";

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
				<SelectItem value="START_TIME_ASC">Newest to oldest</SelectItem>
				<SelectItem value="START_TIME_DESC">Oldest to newest</SelectItem>
				<SelectItem value="NAME_ASC">A to Z</SelectItem>
				<SelectItem value="NAME_DESC">Z to A</SelectItem>
			</SelectContent>
		</Select>
	);
};
