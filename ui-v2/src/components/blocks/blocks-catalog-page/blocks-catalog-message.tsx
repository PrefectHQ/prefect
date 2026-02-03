import { Card } from "@/components/ui/card";
import { DOCS_LINKS } from "@/components/ui/docs-link";

export const BlocksCatalogMessage = () => {
	return (
		<Card className="p-4">
			<p className="text-sm">
				Can&apos;t find a block for your service? Check out the{" "}
				<a
					className="underline text-blue-600 hover:text-blue-800 visited:text-purple-600"
					href={DOCS_LINKS["integrations-guide"]}
				>
					docs
				</a>{" "}
				for a full list of integrations in the SDK
			</p>
		</Card>
	);
};
