import { Flex } from "@/components/ui/flex";
import { useListGlobalConcurrencyLimits } from "@/hooks/global-concurrency-limits";
import { useState } from "react";
import { CreateOrEditLimitDialog } from "./create-or-edit-limit-dialog";
import { GlobalConcurrencyLimitEmptyState } from "./global-concurrency-limit-empty-state";
import { GlobalConcurrencyLimitsHeader } from "./global-concurrency-limits-header";

export const GlobalConcurrencyView = () => {
	const [openDialog, setOpenDialog] = useState(false);

	const { data } = useListGlobalConcurrencyLimits();

	const openAddDialog = () => setOpenDialog(true);
	const closeAddDialog = () => setOpenDialog(false);

	return (
		<>
			{data.length === 0 ? (
				<GlobalConcurrencyLimitEmptyState onAdd={openAddDialog} />
			) : (
				<Flex flexDirection="column" gap={2}>
					<GlobalConcurrencyLimitsHeader onAdd={openAddDialog} />
					<div>TODO</div>
					<ul>
						{data.map((limit) => (
							<li key={limit.id}>{JSON.stringify(limit)}</li>
						))}
					</ul>
				</Flex>
			)}
			<CreateOrEditLimitDialog
				open={openDialog}
				onOpenChange={setOpenDialog}
				limitToUpdate={undefined /** TODO:  */}
				onSubmit={closeAddDialog}
			/>
		</>
	);
};
