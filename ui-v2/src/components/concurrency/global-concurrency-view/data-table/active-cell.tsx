import { useToast } from "@/hooks/use-toast";
import type { CellContext } from "@tanstack/react-table";

import { Switch } from "@/components/ui/switch";
import {
	type GlobalConcurrencyLimit,
	useUpdateGlobalConcurrencyLimit,
} from "@/hooks/global-concurrency-limits";

export const ActiveCell = (
	props: CellContext<GlobalConcurrencyLimit, boolean>,
) => {
	const { toast } = useToast();
	const { updateGlobalConcurrencyLimit } = useUpdateGlobalConcurrencyLimit();

	const handleCheckedChange = (checked: boolean, id: string | undefined) => {
		if (!id) {
			throw new Error("Expecting 'id' of global concurrent limit");
		}

		updateGlobalConcurrencyLimit(
			{
				id_or_name: id,
				active: checked,
			},
			{
				onSuccess: () => {
					toast({ description: "Concurrency limit updated" });
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while updating active field.";
					console.error(message);
				},
			},
		);
	};

	const rowActive = props.getValue();
	const rowId = props.row.original.id;

	return (
		<Switch
			checked={rowActive}
			onCheckedChange={(checked) => handleCheckedChange(checked, rowId)}
		/>
	);
};
