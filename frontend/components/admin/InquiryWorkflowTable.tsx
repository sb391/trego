"use client";

import { Fragment, useMemo, useState } from "react";

import type { InquiryRecord } from "../../lib/inquiries";

const STATUS_OPTIONS = ["new", "contacted", "qualified", "closed"] as const;

type WorkflowRowState = {
  status: string;
  ownerEmail: string;
  internalNote: string;
  eventNote: string;
};

export function InquiryWorkflowTable({
  initialRows,
  workflowEnabled,
}: {
  initialRows: InquiryRecord[];
  workflowEnabled: boolean;
}) {
  const [rows, setRows] = useState(initialRows);
  const [openId, setOpenId] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [feedbackById, setFeedbackById] = useState<Record<string, string>>({});
  const [drafts, setDrafts] = useState<Record<string, WorkflowRowState>>(() =>
    Object.fromEntries(
      initialRows.map((row) => [
        row.id,
        {
          status: row.status,
          ownerEmail: row.owner_email ?? "",
          internalNote: row.internal_note ?? "",
          eventNote: "",
        },
      ]),
    ),
  );

  const rowCount = rows.length;
  const workflowHint = useMemo(
    () =>
      workflowEnabled
        ? "Status changes, notes, and ownership updates save directly into Supabase."
        : "Workflow updates unlock once Supabase admin mode is connected.",
    [workflowEnabled],
  );

  function formatDate(value?: string | null): string {
    if (!value) {
      return "—";
    }

    return new Intl.DateTimeFormat("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  }

  function truncate(value: string, length: number): string {
    if (value.length <= length) {
      return value;
    }

    return `${value.slice(0, length - 1)}…`;
  }

  function updateDraft(id: string, patch: Partial<WorkflowRowState>) {
    setDrafts((current) => ({
      ...current,
      [id]: {
        ...current[id],
        ...patch,
      },
    }));
  }

  async function handleSave(id: string) {
    if (!workflowEnabled) {
      return;
    }

    const draft = drafts[id];
    if (!draft) {
      return;
    }

    setSavingId(id);
    setFeedbackById((current) => ({ ...current, [id]: "" }));

    const response = await fetch(`/api/admin/inquiries/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        status: draft.status,
        ownerEmail: draft.ownerEmail,
        internalNote: draft.internalNote,
        eventNote: draft.eventNote,
      }),
    });

    const payload = (await response.json().catch(() => null)) as
      | { ok?: boolean; inquiry?: InquiryRecord; error?: string }
      | null;

    if (!response.ok || !payload?.ok || !payload.inquiry) {
      setFeedbackById((current) => ({
        ...current,
        [id]: payload?.error ?? "Unable to save the inquiry workflow.",
      }));
      setSavingId(null);
      return;
    }

    setRows((current) => current.map((row) => (row.id === id ? payload.inquiry! : row)));
    setDrafts((current) => ({
      ...current,
      [id]: {
        status: payload.inquiry!.status,
        ownerEmail: payload.inquiry!.owner_email ?? "",
        internalNote: payload.inquiry!.internal_note ?? "",
        eventNote: "",
      },
    }));
    setFeedbackById((current) => ({ ...current, [id]: "Workflow updated." }));
    setSavingId(null);
  }

  return (
    <section className="rounded-[1.5rem] border border-[#ece2e6] bg-white shadow-[0_16px_34px_rgba(10,37,64,0.04)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#f0e5e3] px-6 py-4">
        <div>
          <div className="text-[0.86rem] font-semibold uppercase tracking-[0.18em] text-[#90a2b6]">Inquiry workflow</div>
          <div className="mt-1 text-[0.92rem] leading-6 text-[#66788c]">{workflowHint}</div>
        </div>
        <div className="text-[0.86rem] font-semibold uppercase tracking-[0.18em] text-[#90a2b6]">{rowCount} records</div>
      </div>

      {rows.length === 0 ? (
        <div className="px-6 py-12 text-center text-[0.95rem] leading-7 text-[#69798b]">
          No inquiries have been captured yet.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-left">
            <thead className="bg-[#fcfaf7] text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#93a3b7]">
              <tr>
                {["Submitted", "Contact", "Company", "Service", "Status", "Workflow"].map((header) => (
                  <th key={header} className="px-6 py-4">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#f2e7e4] text-[0.95rem] text-[#243047]">
              {rows.map((row) => {
                const draft = drafts[row.id];
                const isOpen = openId === row.id;
                return (
                  <Fragment key={row.id}>
                    <tr key={row.id} className="align-top">
                      <td className="whitespace-nowrap px-6 py-5 text-[#66788c]">{formatDate(row.created_at)}</td>
                      <td className="px-6 py-5">
                        <div className="font-semibold">{row.full_name}</div>
                        <div className="mt-1 text-[0.88rem] text-[#66788c]">{row.email}</div>
                        {row.phone ? <div className="mt-1 text-[0.84rem] text-[#8da0b4]">{row.phone}</div> : null}
                      </td>
                      <td className="px-6 py-5">
                        <div className="font-semibold">{row.company}</div>
                        {row.source_page ? <div className="mt-1 text-[0.88rem] text-[#66788c]">{row.source_page}</div> : null}
                      </td>
                      <td className="px-6 py-5">{row.inquiry_type}</td>
                      <td className="px-6 py-5">
                        <span className="rounded-full border border-[#eadbd4] bg-[#fff8f4] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-[#a65f41]">
                          {row.status}
                        </span>
                        <div className="mt-3 space-y-1 text-[0.82rem] leading-5 text-[#8a98aa]">
                          <div>Owner: {row.owner_email || "Unassigned"}</div>
                          <div>Updated: {formatDate(row.last_status_changed_at ?? row.updated_at)}</div>
                        </div>
                      </td>
                      <td className="min-w-[16rem] px-6 py-5">
                        <div className="space-y-3">
                          <div className="text-[0.9rem] leading-6 text-[#66788c]">{truncate(row.message, 120)}</div>
                          <button
                            type="button"
                            onClick={() => setOpenId(isOpen ? null : row.id)}
                            className="interactive-press inline-flex items-center justify-center rounded-full border border-[#dfd2d3] bg-white px-4 py-2 text-[0.74rem] font-semibold uppercase tracking-[0.12em] text-[#5f6f82]"
                          >
                            {isOpen ? "Hide workflow" : "Manage workflow"}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {isOpen ? (
                      <tr>
                        <td colSpan={6} className="bg-[#fffcfa] px-6 py-5">
                          <div className="grid gap-4 lg:grid-cols-[0.9fr_0.9fr_1.2fr_auto]">
                            <label className="grid gap-2">
                              <span className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#95a4b6]">Status</span>
                              <select
                                value={draft.status}
                                onChange={(event) => updateDraft(row.id, { status: event.target.value })}
                                className="rounded-[0.95rem] border border-[#e4d9de] bg-white px-4 py-3 text-[0.98rem] text-[#182039] outline-none transition focus:border-[#d1c2c7]"
                                disabled={!workflowEnabled || savingId === row.id}
                              >
                                {STATUS_OPTIONS.map((status) => (
                                  <option key={status} value={status}>
                                    {status}
                                  </option>
                                ))}
                              </select>
                            </label>

                            <label className="grid gap-2">
                              <span className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#95a4b6]">Owner email</span>
                              <input
                                type="email"
                                value={draft.ownerEmail}
                                onChange={(event) => updateDraft(row.id, { ownerEmail: event.target.value })}
                                placeholder="owner@tregocapital.com"
                                className="rounded-[0.95rem] border border-[#e4d9de] bg-white px-4 py-3 text-[0.98rem] text-[#182039] outline-none transition focus:border-[#d1c2c7]"
                                disabled={!workflowEnabled || savingId === row.id}
                              />
                            </label>

                            <div className="grid gap-4 sm:grid-cols-2">
                              <label className="grid gap-2">
                                <span className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#95a4b6]">Internal note</span>
                                <textarea
                                  value={draft.internalNote}
                                  onChange={(event) => updateDraft(row.id, { internalNote: event.target.value })}
                                  placeholder="Current context, next action, or qualification note."
                                  className="min-h-[112px] rounded-[0.95rem] border border-[#e4d9de] bg-white px-4 py-3 text-[0.98rem] text-[#182039] outline-none transition focus:border-[#d1c2c7]"
                                  disabled={!workflowEnabled || savingId === row.id}
                                />
                              </label>

                              <label className="grid gap-2">
                                <span className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#95a4b6]">Status event note</span>
                                <textarea
                                  value={draft.eventNote}
                                  onChange={(event) => updateDraft(row.id, { eventNote: event.target.value })}
                                  placeholder="Optional note to add in inquiry status history."
                                  className="min-h-[112px] rounded-[0.95rem] border border-[#e4d9de] bg-white px-4 py-3 text-[0.98rem] text-[#182039] outline-none transition focus:border-[#d1c2c7]"
                                  disabled={!workflowEnabled || savingId === row.id}
                                />
                              </label>
                            </div>

                            <div className="flex flex-col items-start justify-end gap-3">
                              <button
                                type="button"
                                onClick={() => handleSave(row.id)}
                                disabled={!workflowEnabled || savingId === row.id}
                                className="interactive-press inline-flex min-h-12 items-center justify-center rounded-[0.95rem] border border-[#7f3922] bg-[#853921] px-5 py-3 text-[0.76rem] font-semibold uppercase tracking-[0.1em] text-white shadow-[0_12px_22px_rgba(133,57,33,0.22)] disabled:cursor-not-allowed disabled:opacity-70"
                              >
                                {savingId === row.id ? "Saving..." : "Save workflow"}
                              </button>
                              {feedbackById[row.id] ? (
                                <div className="max-w-[16rem] text-[0.84rem] leading-6 text-[#7b6e79]">{feedbackById[row.id]}</div>
                              ) : null}
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
