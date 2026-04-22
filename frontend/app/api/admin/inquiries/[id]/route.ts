import { NextResponse } from "next/server";

import { getAuthenticatedAdmin } from "../../../../../lib/admin/auth";
import { isMissingColumnError } from "../../../../../lib/supabase/schema-compat";
import { getSupabaseAdminClient } from "../../../../../lib/supabase/admin";
import type { InquiryRecord } from "../../../../../lib/inquiries";

const STATUS_OPTIONS = new Set(["new", "contacted", "qualified", "closed"]);

export async function PATCH(request: Request, context: { params: Promise<{ id: string }> }) {
  const adminUser = await getAuthenticatedAdmin();
  if (!adminUser) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }

  const client = getSupabaseAdminClient();
  if (!client) {
    return NextResponse.json(
      { ok: false, error: "Supabase admin mode is not configured yet." },
      { status: 503 },
    );
  }

  const { id } = await context.params;
  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object") {
    return NextResponse.json({ ok: false, error: "Invalid workflow payload." }, { status: 400 });
  }

  const nextStatus = typeof payload.status === "string" ? payload.status.trim().toLowerCase() : "";
  const ownerEmail =
    typeof payload.ownerEmail === "string" && payload.ownerEmail.trim().length > 0
      ? payload.ownerEmail.trim().toLowerCase()
      : null;
  const internalNote =
    typeof payload.internalNote === "string" && payload.internalNote.trim().length > 0
      ? payload.internalNote.trim()
      : null;
  const eventNote =
    typeof payload.eventNote === "string" && payload.eventNote.trim().length > 0
      ? payload.eventNote.trim()
      : null;

  if (!STATUS_OPTIONS.has(nextStatus)) {
    return NextResponse.json({ ok: false, error: "Invalid inquiry status." }, { status: 400 });
  }

  const { data: existingInquiry, error: existingError } = await client
    .from("inquiries")
    .select("*")
    .eq("id", id)
    .single();

  if (existingError || !existingInquiry) {
    return NextResponse.json({ ok: false, error: "Inquiry not found." }, { status: 404 });
  }

  const previousStatus = existingInquiry.status ?? null;
  const now = new Date().toISOString();

  const updatePayload = {
    status: nextStatus,
    owner_email: ownerEmail,
    internal_note: internalNote,
    last_status_changed_at: previousStatus !== nextStatus ? now : existingInquiry.last_status_changed_at ?? now,
  };

  const { data: updatedInquiry, error: updateError } = await client
    .from("inquiries")
    .update(updatePayload)
    .eq("id", id)
    .select("*")
    .single();

  if (
    updateError &&
    isMissingColumnError(updateError, "inquiries", ["owner_email", "internal_note", "last_status_changed_at"])
  ) {
    const { data: legacyInquiry, error: legacyError } = await client
      .from("inquiries")
      .update({ status: nextStatus })
      .eq("id", id)
      .select("*")
      .single();

    if (!legacyError && legacyInquiry) {
      if (previousStatus !== nextStatus || eventNote) {
        await client.from("inquiry_status_events").insert({
          inquiry_id: id,
          previous_status: previousStatus,
          next_status: nextStatus,
          note: eventNote,
          changed_by_email: adminUser.email,
        });
      }

      return NextResponse.json({
        ok: true,
        inquiry: legacyInquiry as InquiryRecord,
        warning: "Inquiry status updated, but workflow migration is still pending.",
      });
    }
  }

  if (updateError || !updatedInquiry) {
    return NextResponse.json(
      { ok: false, error: updateError?.message ?? "Unable to update inquiry workflow." },
      { status: 500 },
    );
  }

  if (previousStatus !== nextStatus || eventNote) {
    await client.from("inquiry_status_events").insert({
      inquiry_id: id,
      previous_status: previousStatus,
      next_status: nextStatus,
      note: eventNote,
      changed_by_email: adminUser.email,
    });
  }

  return NextResponse.json({ ok: true, inquiry: updatedInquiry as InquiryRecord });
}
