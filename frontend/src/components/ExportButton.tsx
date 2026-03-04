import api from "../api/client";

interface Props {
  runId: number;
  format: "csv" | "json";
}

export default function ExportButton({ runId, format }: Props) {
  const handleExport = async () => {
    const resp = await api.get(`/export/${format}?run_id=${runId}`, {
      responseType: format === "csv" ? "blob" : "json",
    });

    let blob: Blob;
    if (format === "csv") {
      blob = new Blob([resp.data], { type: "text/csv" });
    } else {
      blob = new Blob([JSON.stringify(resp.data, null, 2)], {
        type: "application/json",
      });
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `evi_run_${runId}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <button
      onClick={handleExport}
      className="px-3 py-1 text-xs font-medium rounded border border-gray-300 hover:bg-gray-100"
    >
      Export {format.toUpperCase()}
    </button>
  );
}
