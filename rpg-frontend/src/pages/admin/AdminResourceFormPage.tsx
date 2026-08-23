import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { ErrorState, Skeleton } from "@/components/ui";
import { ImageUploadField } from "@/components/admin/ImageUploadField";
import { RESOURCES, type FieldConfig } from "@/admin/resources";

type FormValue = string | number | boolean | string[];
type FormState = Record<string, FormValue>;

function defaultFor(field: FieldConfig): FormValue {
  if (field.defaultValue !== undefined) return field.defaultValue;
  if (field.type === "checkbox") return true;
  if (field.type === "multiselect") return [];
  if (field.type === "number") return 0;
  return "";
}

function buildInitialState(fields: FieldConfig[], existing?: Record<string, unknown>): FormState {
  const state: FormState = {};
  for (const field of fields) {
    const readKey = field.sourceKey ?? field.key;
    if (existing && readKey in existing) {
      const raw = existing[readKey];
      if (field.type === "multiselect" && Array.isArray(raw)) {
        // e.g. affixes come back as [{id, stat_type}] — reduce to the stat_type list
        state[field.key] = raw.map((item) =>
          typeof item === "string" ? item : (item as { stat_type: string }).stat_type,
        );
      } else {
        state[field.key] = raw as FormValue;
      }
    } else {
      state[field.key] = defaultFor(field);
    }
  }
  return state;
}

function FieldInput({
  field,
  value,
  onChange,
  disabled,
  raceOptions,
  classOptions,
}: {
  field: FieldConfig;
  value: FormValue;
  onChange: (v: FormValue) => void;
  disabled: boolean;
  raceOptions: { value: string; label: string }[];
  classOptions: { value: string; label: string }[];
}) {
  const baseClass = "w-full rounded-md border border-hairline bg-bg-raised px-3 py-2 text-[13px] text-ink outline-none disabled:opacity-50";

  if (field.type === "textarea") {
    return (
      <textarea
        value={String(value)}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        rows={2}
        className={baseClass}
      />
    );
  }
  if (field.type === "checkbox") {
    return (
      <input
        type="checkbox"
        checked={Boolean(value)}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
      />
    );
  }
  if (field.type === "number") {
    return (
      <input
        type="number"
        step={field.step ?? "1"}
        value={String(value)}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
        className={baseClass}
      />
    );
  }
  if (field.type === "select" || field.type === "race-select" || field.type === "class-select") {
    const options =
      field.type === "race-select" ? raceOptions : field.type === "class-select" ? classOptions : (field.options ?? []);
    return (
      <select
        value={String(value)}
        onChange={(e) => onChange(field.type === "select" ? e.target.value : Number(e.target.value))}
        disabled={disabled}
        className={baseClass}
      >
        <option value="">—</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    );
  }
  if (field.type === "multiselect") {
    const selected = Array.isArray(value) ? value : [];
    return (
      <div className="flex flex-wrap gap-1.5">
        {(field.options ?? []).map((o) => {
          const active = selected.includes(o.value);
          return (
            <button
              key={o.value}
              type="button"
              disabled={disabled}
              onClick={() =>
                onChange(active ? selected.filter((v) => v !== o.value) : [...selected, o.value])
              }
              className={`rounded-md border px-2.5 py-1 font-mono text-[10.5px] disabled:opacity-50 ${
                active ? "border-ember bg-ember/15 text-ember-bright" : "border-hairline bg-bg-raised text-ink-mute"
              }`}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    );
  }
  return (
    <input
      value={String(value)}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className={baseClass}
    />
  );
}

export function AdminResourceFormPage() {
  const { resource, id } = useParams<{ resource: string; id?: string }>();
  const config = resource ? RESOURCES[resource] : undefined;
  const navigate = useNavigate();

  const isEdit = Boolean(id);
  const list = config?.hooks.useList();
  const create = config?.hooks.useCreate();
  const update = config?.hooks.useUpdate();

  const races = RESOURCES.races.hooks.useList();
  const classes = RESOURCES.classes.hooks.useList();

  const existing = isEdit ? (list?.data as Record<string, unknown>[] | undefined)?.find((r) => r.id === Number(id)) : undefined;
  const [form, setForm] = useState<FormState>({});

  useEffect(() => {
    if (config && (!isEdit || existing)) {
      setForm(buildInitialState(config.fields, existing));
    }
  }, [config, existing, isEdit]);

  if (!config) return <Navigate to="/admin/catalog" replace />;
  if (isEdit && list?.isPending) return <Skeleton className="h-64" />;
  if (isEdit && !existing && !list?.isPending) return <ErrorState error={new Error("not found")} />;

  const mutation = isEdit ? update! : create!;

  function submit() {
    const payload: Record<string, unknown> = {};
    for (const field of config!.fields) {
      if (isEdit && field.createOnly) continue;
      payload[field.key] = form[field.key];
    }
    if (isEdit) {
      update!.mutate({ id: Number(id), payload }, { onSuccess: () => navigate(`/admin/catalog/${config!.key}`) });
    } else {
      create!.mutate(payload, { onSuccess: () => navigate(`/admin/catalog/${config!.key}`) });
    }
  }

  const raceOptions = (races.data as { id: number; name: string }[] | undefined)?.map((r) => ({
    value: String(r.id),
    label: r.name,
  })) ?? [];
  const classOptions = (classes.data as { id: number; name: string }[] | undefined)?.map((c) => ({
    value: String(c.id),
    label: c.name,
  })) ?? [];

  return (
    <div className="max-w-lg">
      <h1 className="mb-4 font-display text-2xl font-semibold text-ink">
        {isEdit ? `Изменить: ${config.label}` : `Новый: ${config.label}`}
      </h1>

      <div className="flex flex-col gap-3">
        {isEdit && config.imageUploadKind && existing && (
          <ImageUploadField
            basePath={config.basePath}
            resourceId={Number(id)}
            currentImagePath={(existing.image_path as string | null) ?? null}
            queryKey={config.key}
          />
        )}

        {config.fields.map((field) => (
          <label key={field.key} className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase text-ink-dim">
              {field.label}
              {isEdit && field.createOnly && " (только при создании)"}
            </span>
            <FieldInput
              field={field}
              value={form[field.key] ?? defaultFor(field)}
              onChange={(v) => setForm((f) => ({ ...f, [field.key]: v }))}
              disabled={isEdit && Boolean(field.createOnly)}
              raceOptions={raceOptions}
              classOptions={classOptions}
            />
          </label>
        ))}

        {mutation.isError && <ErrorState error={mutation.error} />}

        <button
          onClick={submit}
          disabled={mutation.isPending}
          className="mt-2 rounded-md bg-gradient-to-b from-ember-bright to-ember py-2.5 font-mono text-[12px] font-bold text-[#1D1204] disabled:opacity-40"
        >
          {mutation.isPending ? "Сохранение..." : isEdit ? "Сохранить" : "Создать"}
        </button>
      </div>
    </div>
  );
}
