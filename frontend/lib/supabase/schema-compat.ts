import type { PostgrestError } from "@supabase/supabase-js";

function normalizeMessage(error: Pick<PostgrestError, "message" | "details" | "hint"> | null | undefined) {
  return [error?.message, error?.details, error?.hint]
    .filter((value): value is string => typeof value === "string" && value.length > 0)
    .join(" ")
    .toLowerCase();
}

export function isMissingColumnError(
  error: Pick<PostgrestError, "message" | "details" | "hint"> | null | undefined,
  table: string,
  columns: string[],
) {
  const message = normalizeMessage(error);
  if (!message) {
    return false;
  }

  return columns.some((column) => {
    const normalizedTable = table.toLowerCase();
    const normalizedColumn = column.toLowerCase();

    return (
      message.includes(`'${normalizedColumn}' column of '${normalizedTable}'`) ||
      message.includes(`column "${normalizedColumn}"`) ||
      message.includes(`column ${normalizedColumn}`) ||
      (message.includes(normalizedColumn) && message.includes(normalizedTable))
    );
  });
}
