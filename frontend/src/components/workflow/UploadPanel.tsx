import { useRef, useState } from 'react';
import { UploadCloud } from 'lucide-react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';

interface UploadPanelProps {
  title: string;
  description: string;
  // 接受的副檔名，例如 ".csv,.xlsx,.json"
  accept: string;
  idleLabel: string;
  loadingLabel: string;
  // 提示可接受的檔案格式
  selectedFileLabel: string;
  onUpload: (file: File) => Promise<any>;
  // 上傳成功後由父層決定如何呈現結果
  renderResult?: (result: any) => React.ReactNode;
}

// 事件工單與技術文件共用的上傳面板，自行管理檔案 / 載入 / 結果 / 錯誤狀態。
export function UploadPanel({
  title,
  description,
  accept,
  idleLabel,
  loadingLabel,
  selectedFileLabel,
  onUpload,
  renderResult,
}: UploadPanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setResult(null);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setError(null);
    setResult(null);

    try {
      const res = await onUpload(file);
      setResult(res);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card title={title} description={description}>
        <div className="flex flex-col space-y-4">
          {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-600">{error}</div>}

          <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 p-8">
            <UploadCloud className="mb-3 h-8 w-8 text-slate-400" />
            <input
              type="file"
              ref={fileInputRef}
              accept={accept}
              onChange={handleFileChange}
              className="hidden"
              id="workflow-file-upload"
            />
            <label
              htmlFor="workflow-file-upload"
              className="inline-flex cursor-pointer items-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 focus:outline-none"
            >
              選擇檔案
            </label>
            <p className="mt-3 text-sm text-slate-500">{file ? file.name : selectedFileLabel}</p>
          </div>

          <div className="flex justify-end">
            <Button onClick={handleUpload} disabled={!file || isUploading}>
              {isUploading ? loadingLabel : idleLabel}
            </Button>
          </div>
        </div>
      </Card>

      {result && renderResult && <div>{renderResult(result)}</div>}
    </div>
  );
}
