import { STATE_NAME_TO_TYPE } from "@/api/flow-runs/constants";
import { Badge } from "@/components/ui/badge";
import { StateBadge } from "@/components/ui/state-badge";

export function StateNameBadge({ name }: { name: string }) {
	if (Object.hasOwn(STATE_NAME_TO_TYPE, name)) {
		return (
			<StateBadge
				name={name}
				type={STATE_NAME_TO_TYPE[name as keyof typeof STATE_NAME_TO_TYPE]}
			/>
		);
	}
	// A custom name can occur under multiple types; do not assign it a type here.
	return <Badge variant="secondary">{name}</Badge>;
}
