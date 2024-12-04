import { Icon } from "@/components/ui/icons";
import { IconInput } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { TagsInput } from "@/components/ui/tags-input";
import useDebounce from "@/hooks/use-debounce";
import { useEffect, useState } from "react";

type VariablesDataTableSearchProps = {
	initialSearchValue: string;
	onNameSearchChange: (value: string) => void;
	onSortChange: (value: string) => void;
};

export const VariablesDataTableSearch = ({
	initialSearchValue,
	onNameSearchChange,
	onSortChange,
}: VariablesDataTableSearchProps) => {
	const [searchValue, setSearchValue] = useState(initialSearchValue);
	const debouncedSearchValue = useDebounce(searchValue, 500);

	useEffect(() => {
		onNameSearchChange(debouncedSearchValue);
	}, [debouncedSearchValue, onNameSearchChange]);

	return (
		<div className="flex items-center gap-2 w-1/2 max-w-md">
			<IconInput
				Icon={() => <Icon id="Search" />}
				placeholder="Search variables"
				value={searchValue}
				onChange={(e) => setSearchValue(e.target.value)}
			/>
			<TagsInput placeholder="Tags" />
			<Select
				onValueChange={(value) => onSortChange(value)}
				defaultValue="CREATED_DESC"
			>
				<SelectTrigger className="w-1/4">
					<SelectValue placeholder="Sort by" />
				</SelectTrigger>
				<SelectContent>
					<SelectItem value="CREATED_DESC">Created</SelectItem>
					<SelectItem value="UPDATED_DESC">Updated</SelectItem>
					<SelectItem value="NAME_ASC">A to Z</SelectItem>
					<SelectItem value="NAME_DESC">Z to A</SelectItem>
				</SelectContent>
			</Select>
		</div>
	);
};
