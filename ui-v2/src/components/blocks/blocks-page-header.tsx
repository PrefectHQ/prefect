import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { Link } from "@tanstack/react-router";

export function BlocksPageHeader() {
	return (
		<div className="flex gap-2 items-center">
			<Typography className="font-semibold">Blocks</Typography>
			<Link to="/blocks/catalog">
				<Button
					size="icon"
					className="size-7"
					variant="outline"
					aria-label="add block document"
				>
					<Icon id="Plus" className="size-4" />
				</Button>
			</Link>
		</div>
	);
}
