export type JSONValue =
	| string
	| number
	| boolean
	| Record<string, never>
	| unknown[]
	| null;
