import { useState } from "react";
import { GlobalConcurrencyLimitsHeader } from "./global-concurrency-limits-header";

export const GlobalConcurrencyView = () => {
	const [showAddDialog, setShowAddDialog] = useState(false);

	const openAddDialog = () => setShowAddDialog(true);
	const closeAddDialog = () => setShowAddDialog(false);

	return (
		<>
			<div className="flex flex-col gap-2">
				<GlobalConcurrencyLimitsHeader onAdd={openAddDialog} />
			</div>
			{showAddDialog && <div onClick={closeAddDialog}>TODO: DIALOG</div>}
		</>
	);
};
