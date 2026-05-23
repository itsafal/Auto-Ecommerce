"use client";

import { useEffect, useState } from "react";
import { getLLMConfig, type LLMConfig, updateLLMConfig } from "@/lib/api";
import styles from "./ModelPicker.module.css";

const MODEL_OPTIONS: Record<string, string[]> = {
  anthropic: ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"],
  gemini: ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"],
  portkey: ["@vertexai/gemini-3.5-flash"]
};

const PROVIDER_LABELS: Record<string, string> = {
  auto: "Auto (Portkey → Claude → Gemini)",
  anthropic: "Claude (Anthropic)",
  gemini: "Gemini (Google direct)",
  portkey: "Portkey (NYU gateway)"
};

export function ModelPicker() {
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [provider, setProvider] = useState<string>("auto");
  const [model, setModel] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [statusKind, setStatusKind] = useState<"" | "success" | "error">("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getLLMConfig()
      .then((cfg) => {
        setConfig(cfg);
        setProvider(cfg.provider);
        setModel(modelForProvider(cfg, cfg.provider));
      })
      .catch((err) => {
        setStatus(err.message);
        setStatusKind("error");
      });
  }, []);

  function modelForProvider(cfg: LLMConfig, p: string): string {
    if (p === "anthropic") return cfg.anthropic_model;
    if (p === "gemini" || p === "google") return cfg.gemini_model;
    if (p === "portkey") return cfg.portkey_model;
    return "";
  }

  const apply = async (nextProvider: string, nextModel: string) => {
    setBusy(true);
    setStatus("Updating...");
    setStatusKind("");
    try {
      const patch: Parameters<typeof updateLLMConfig>[0] = { provider: nextProvider as LLMConfig["provider"] };
      if (nextProvider === "anthropic" && nextModel) patch.anthropic_model = nextModel;
      if (nextProvider === "gemini" && nextModel) patch.gemini_model = nextModel;
      if (nextProvider === "portkey" && nextModel) patch.portkey_model = nextModel;

      const updated = await updateLLMConfig(patch);
      setConfig(updated);
      setProvider(updated.provider);
      setModel(modelForProvider(updated, updated.provider));
      setStatus(`Now using ${updated.auto_chain_winner}`);
      setStatusKind("success");
    } catch (err) {
      setStatus((err as Error).message);
      setStatusKind("error");
    } finally {
      setBusy(false);
    }
  };

  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    setProvider(next);
    const nextModel = config ? modelForProvider(config, next) || (MODEL_OPTIONS[next]?.[0] ?? "") : "";
    setModel(nextModel);
    void apply(next, nextModel);
  };

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    setModel(next);
    void apply(provider, next);
  };

  if (!config) {
    return (
      <div className={styles.card}>
        <span className={styles.title}>Model</span>
        <span className={styles.status}>{status || "Loading..."}</span>
      </div>
    );
  }

  const modelOptions = MODEL_OPTIONS[provider] ?? [];
  const showModelPicker = provider !== "auto" && modelOptions.length > 0;

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.title}>Agent Model</span>
        <span className={styles.winner}>{config.auto_chain_winner}</span>
      </div>
      <div className={styles.row}>
        <div className={styles.field}>
          <span className={styles.label}>Provider</span>
          <select
            className={styles.select}
            value={provider}
            onChange={handleProviderChange}
            disabled={busy}
          >
            {Object.keys(PROVIDER_LABELS).map((key) => (
              <option key={key} value={key} disabled={key !== "auto" && !config.keys_set[key as "anthropic" | "portkey" | "gemini"]}>
                {PROVIDER_LABELS[key]}
                {key !== "auto" && !config.keys_set[key as "anthropic" | "portkey" | "gemini"] ? " (no key)" : ""}
              </option>
            ))}
          </select>
        </div>
        {showModelPicker && (
          <div className={styles.field}>
            <span className={styles.label}>Model</span>
            <select className={styles.select} value={model} onChange={handleModelChange} disabled={busy}>
              {modelOptions.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      <span className={`${styles.status} ${statusKind === "error" ? styles.error : statusKind === "success" ? styles.success : ""}`}>
        {status}
      </span>
    </div>
  );
}
