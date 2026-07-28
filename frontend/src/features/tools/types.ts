export interface ToolInfo {
  name: string;
  description: string;
  category: string;
  permissions: string[];
  dependencies: string[];
  version: string;
  origin: string;
  tags: string[];
  input_schema: JsonSchema;
  output_schema: JsonSchema;
}

/** The subset of JSON Schema the marketplace renders. */
export interface JsonSchema {
  properties?: Record<
    string,
    { type?: string; description?: string; default?: unknown }
  >;
  required?: string[];
}

export interface ToolInvokeResult {
  tool: string;
  result: Record<string, unknown>;
}
