import { SearchInput } from "@/components/ui/input";

type SearchProps = {
	nameSearchValue?: string;
	onNameSearchChange: (value?: string) => void;
};

export const Search = ({
	nameSearchValue,
	onNameSearchChange,
}: SearchProps) => {
	return (
		<div className="sm:col-span-2 md:col-span-2 lg:col-span-4">
			<SearchInput
				placeholder="Search work pools"
				value={nameSearchValue}
				onChange={(e) => onNameSearchChange(e.target.value)}
			/>
		</div>
	);
};
