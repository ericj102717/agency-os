import { useState } from "react";
import { X, UserPlus, DollarSign, Share2, FileText, Loader2, CheckCircle, AlertCircle, UserCheck } from "lucide-react";
import { Card, CardContent } from "@/components/ui-widgets";
import { API_BASE, mutationFetch } from "@/lib/queryClient";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

type ModalType = "add-lead" | "add-client" | "log-revenue" | "add-referral" | "add-note" | null;

interface ModalState {
  type: ModalType;
  open: boolean;
}

let openModalFn: ((type: ModalType) => void) | null = null;

export function openModal(type: ModalType) {
  openModalFn?.(type);
}

export function ActionModals() {
  const [modal, setModal] = useState<ModalState>({ type: null, open: false });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const queryClient = useQueryClient();

  openModalFn = (type: ModalType) => {
    setModal({ type, open: true });
    setResult(null);
  };

  const close = () => {
    setModal({ type: null, open: false });
    setResult(null);
  };

  const submit = async (endpoint: string, payload: Record<string, unknown>, method: string = "POST") => {
    setSubmitting(true);
    setResult(null);
    try {
      const res = await mutationFetch(`/api/${endpoint}`, {
        method,
        body: payload,
      });
      const data = await res.json();
      if (data.status === "ok" || data.status === "success") {
        setResult({ ok: true, message: "Saved successfully" });
        queryClient.invalidateQueries();
        setTimeout(close, 1500);
      } else {
        setResult({ ok: false, message: data.error || "Failed to save" });
      }
    } catch (e) {
      setResult({ ok: false, message: "Network error — could not reach backend" });
    } finally {
      setSubmitting(false);
    }
  };

  if (!modal.open || !modal.type) return null;

  const titles: Record<string, string> = {
    "add-lead": "Add Lead",
    "add-client": "Add Client",
    "log-revenue": "Log Revenue",
    "add-referral": "Add Referral Source",
    "add-note": "Add Note",
  };

  const icons: Record<string, typeof UserPlus> = {
    "add-lead": UserPlus,
    "add-client": UserCheck,
    "log-revenue": DollarSign,
    "add-referral": Share2,
    "add-note": FileText,
  };

  const Icon = icons[modal.type];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" onClick={close}>
      <div
        className="w-full max-w-md rounded-xl bg-card border border-border shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-primary" />
            <h3 className="text-lg font-semibold">{titles[modal.type]}</h3>
          </div>
          <button onClick={close} className="p-1 rounded-lg hover:bg-muted" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5">
          {result ? (
            <div className={cn(
              "flex items-center gap-3 px-4 py-6 rounded-lg",
              result.ok ? "bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-300" : "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300"
            )}>
              {result.ok ? <CheckCircle className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
              {result.message}
            </div>
          ) : modal.type === "add-lead" ? (
            <AddLeadForm onSubmit={(p) => submit("contacts", p)} submitting={submitting} />
          ) : modal.type === "add-client" ? (
            <AddClientForm onSubmit={(p) => submit("contacts", p)} submitting={submitting} />
          ) : modal.type === "log-revenue" ? (
            <LogRevenueForm onSubmit={(p) => submit("revenue", p)} submitting={submitting} />
          ) : modal.type === "add-referral" ? (
            <AddReferralForm onSubmit={(p) => submit("referral-sources", p)} submitting={submitting} />
          ) : modal.type === "add-note" ? (
            <AddNoteForm onSubmit={(p) => submit(`contacts/${p.contact_id}`, { notes: p.note }, "PUT")} submitting={submitting} />
          ) : null}
        </div>
      </div>
    </div>
  );
}

// ---- Form Components ----

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-sm font-medium mb-1 block">{label}</label>
      {children}
    </div>
  );
}

const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/40";

function AddLeadForm({ onSubmit, submitting }: { onSubmit: (p: Record<string, unknown>) => void; submitting: boolean }) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [leadSource, setLeadSource] = useState("");
  const [contactType, setContactType] = useState("lead");

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit({ first_name: firstName, last_name: lastName, email, phone, lead_source: leadSource, contact_type: contactType }); }}
      className="space-y-3"
    >
      <div className="grid grid-cols-2 gap-3">
        <Field label="First Name *">
          <input required value={firstName} onChange={(e) => setFirstName(e.target.value)} className={inputCls} placeholder="Jane" />
        </Field>
        <Field label="Last Name">
          <input value={lastName} onChange={(e) => setLastName(e.target.value)} className={inputCls} placeholder="Smith" />
        </Field>
      </div>
      <Field label="Email">
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} placeholder="jane@example.com" />
      </Field>
      <Field label="Phone">
        <input value={phone} onChange={(e) => setPhone(e.target.value)} className={inputCls} placeholder="(303) 555-0100" />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Lead Source">
          <select value={leadSource} onChange={(e) => setLeadSource(e.target.value)} className={inputCls}>
            <option value="">— Select —</option>
            <option value="referral">Referral</option>
            <option value="website">Website</option>
            <option value="cold_call">Cold Call</option>
            <option value="social_media">Social Media</option>
            <option value="event">Event</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field label="Contact Type">
          <select value={contactType} onChange={(e) => setContactType(e.target.value)} className={inputCls}>
            <option value="lead">Lead</option>
            <option value="prospect">Prospect</option>
            <option value="client">Client</option>
          </select>
        </Field>
      </div>
      <SubmitButton submitting={submitting} />
    </form>
  );
}

function AddClientForm({ onSubmit, submitting }: { onSubmit: (p: Record<string, unknown>) => void; submitting: boolean }) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [leadSource, setLeadSource] = useState("referral");
  const [pipelineStage, setPipelineStage] = useState("client");
  const [notes, setNotes] = useState("");

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          first_name: firstName,
          last_name: lastName,
          email,
          phone,
          lead_source: leadSource,
          contact_type: "client",
          pipeline_stage: pipelineStage,
          client_since: new Date().toISOString().split("T")[0],
          notes,
        });
      }}
      className="space-y-3"
    >
      <div className="grid grid-cols-2 gap-3">
        <Field label="First Name *">
          <input required value={firstName} onChange={(e) => setFirstName(e.target.value)} className={inputCls} placeholder="Jane" />
        </Field>
        <Field label="Last Name">
          <input value={lastName} onChange={(e) => setLastName(e.target.value)} className={inputCls} placeholder="Smith" />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Email">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} placeholder="jane@example.com" />
        </Field>
        <Field label="Phone">
          <input value={phone} onChange={(e) => setPhone(e.target.value)} className={inputCls} placeholder="(303) 555-0100" />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Acquisition Source">
          <select value={leadSource} onChange={(e) => setLeadSource(e.target.value)} className={inputCls}>
            <option value="referral">Referral</option>
            <option value="website">Website</option>
            <option value="cold_call">Cold Call</option>
            <option value="social_media">Social Media</option>
            <option value="event">Event</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field label="Pipeline Stage">
          <select value={pipelineStage} onChange={(e) => setPipelineStage(e.target.value)} className={inputCls}>
            <option value="client">Client</option>
            <option value="onboarding">Onboarding</option>
            <option value="active">Active</option>
            <option value="renewal">Renewal</option>
          </select>
        </Field>
      </div>
      <Field label="Notes">
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} className={cn(inputCls, "min-h-[60px] resize-y")} placeholder="Project details, scope, or notes..." />
      </Field>
      <SubmitButton submitting={submitting} label="Add Client" />
    </form>
  );
}

function LogRevenueForm({ onSubmit, submitting }: { onSubmit: (p: Record<string, unknown>) => void; submitting: boolean }) {
  const [contactId, setContactId] = useState("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [revenueDate, setRevenueDate] = useState(new Date().toISOString().split("T")[0]);

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit({ contact_id: contactId, amount: Number(amount), description, revenue_date: revenueDate }); }}
      className="space-y-3"
    >
      <Field label="Contact ID">
        <input value={contactId} onChange={(e) => setContactId(e.target.value)} className={inputCls} placeholder="CNT-20260817-XXXXXX" />
      </Field>
      <Field label="Amount *">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">$</span>
          <input required type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className={inputCls} placeholder="5000.00" />
        </div>
      </Field>
      <Field label="Description">
        <input value={description} onChange={(e) => setDescription(e.target.value)} className={inputCls} placeholder="Roof installation — residential" />
      </Field>
      <Field label="Date">
        <input type="date" value={revenueDate} onChange={(e) => setRevenueDate(e.target.value)} className={inputCls} />
      </Field>
      <SubmitButton submitting={submitting} label="Log Revenue" />
    </form>
  );
}

function AddReferralForm({ onSubmit, submitting }: { onSubmit: (p: Record<string, unknown>) => void; submitting: boolean }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [status, setStatus] = useState("active");

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit({ name, email, phone, status }); }}
      className="space-y-3"
    >
      <Field label="Source Name *">
        <input required value={name} onChange={(e) => setName(e.target.value)} className={inputCls} placeholder="John Smith" />
      </Field>
      <Field label="Email">
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} placeholder="john@example.com" />
      </Field>
      <Field label="Phone">
        <input value={phone} onChange={(e) => setPhone(e.target.value)} className={inputCls} placeholder="(303) 555-0100" />
      </Field>
      <Field label="Status">
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={inputCls}>
          <option value="active">Active</option>
          <option value="dormant">Dormant</option>
          <option value="champion">Champion</option>
        </select>
      </Field>
      <SubmitButton submitting={submitting} label="Add Referral Source" />
    </form>
  );
}

function AddNoteForm({ onSubmit, submitting }: { onSubmit: (p: { contact_id: string; note: string }) => void; submitting: boolean }) {
  const [contactId, setContactId] = useState("");
  const [note, setNote] = useState("");

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit({ contact_id: contactId, note }); }}
      className="space-y-3"
    >
      <Field label="Contact ID">
        <input value={contactId} onChange={(e) => setContactId(e.target.value)} className={inputCls} placeholder="CNT-20260817-XXXXXX" />
      </Field>
      <Field label="Note *">
        <textarea required value={note} onChange={(e) => setNote(e.target.value)} className={cn(inputCls, "min-h-[100px] resize-y")} placeholder="Called client, discussed roofing project timeline..." />
      </Field>
      <SubmitButton submitting={submitting} label="Save Note" />
    </form>
  );
}

function SubmitButton({ submitting, label = "Save" }: { submitting: boolean; label?: string }) {
  return (
    <button
      type="submit"
      disabled={submitting}
      className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
    >
      {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
      {submitting ? "Saving..." : label}
    </button>
  );
}
