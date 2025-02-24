import {
	Pagination,
	PaginationContent,
	PaginationFirstButton,
	PaginationItem,
	PaginationLastButton,
	PaginationNextButton,
	PaginationPreviousButton,
} from "@/components/ui/pagination";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

const PAGINATION_INCREMENTS = [5, 10, 25, 50];

export type PaginationState = {
	limit: number;
	page: number;
};
export type PaginationStateUpdater = (
	prevState: PaginationState,
) => PaginationState;

type FlowRunsPaginationProps = {
	count: number;
	pages: number;
	pagination: PaginationState;
	onChangePagination: (pagination: PaginationState) => void;
};
export const FlowRunsPagination = ({
	count,
	pages,
	pagination,
	onChangePagination,
}: FlowRunsPaginationProps) => {
	const handleFirstPage = () =>
		onChangePagination({ limit: pagination.limit, page: 1 });
	const handlePreviousPage = () =>
		onChangePagination({ limit: pagination.limit, page: pagination.page - 1 });
	const handleNextPage = () =>
		onChangePagination({ limit: pagination.limit, page: pagination.page + 1 });

	const handleLastPage = () =>
		onChangePagination({ limit: pagination.limit, page: pages });

	const disablePreviousPage = pagination.page <= 1;
	const disableNextPage = pagination.page >= pages;

	const handleChangeLimit = (value: string) => {
		const newLimit = Number(value);
		const newTotalPages = Math.ceil(count / newLimit);
		const newPage = Math.min(pagination.page, newTotalPages);
		onChangePagination({
			limit: newLimit,
			page: newPage,
		});
	};

	return (
		<div className="flex flex-row justify-between items-center">
			<div className="flex flex-row items-center gap-2 text-xs text-muted-foreground">
				<span className="whitespace-nowrap">Items per page</span>
				<Select
					value={String(pagination.limit)}
					onValueChange={handleChangeLimit}
				>
					<SelectTrigger aria-label="Items per page">
						<SelectValue placeholder="Theme" />
					</SelectTrigger>
					<SelectContent>
						{PAGINATION_INCREMENTS.map((increment) => (
							<SelectItem key={increment} value={String(increment)}>
								{increment}
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</div>
			<Pagination className="justify-end">
				<PaginationContent>
					<PaginationItem>
						<PaginationFirstButton
							onClick={handleFirstPage}
							disabled={disablePreviousPage}
						/>
						<PaginationPreviousButton
							onClick={handlePreviousPage}
							disabled={disablePreviousPage}
						/>
					</PaginationItem>
					<PaginationItem className="text-sm">
						Page {pagination.page} of {pages}
					</PaginationItem>
					<PaginationItem>
						<PaginationNextButton
							onClick={handleNextPage}
							disabled={disableNextPage}
						/>
					</PaginationItem>
					<PaginationItem>
						<PaginationLastButton
							onClick={handleLastPage}
							disabled={disableNextPage}
						/>
					</PaginationItem>
				</PaginationContent>
			</Pagination>
		</div>
	);
};
