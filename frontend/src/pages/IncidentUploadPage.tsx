import { useState, useRef } from 'react';
import { Card } from '../components/ui/Card';
import { UploadCloud, ShieldAlert, ArrowRight } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { useProject } from '../context/ProjectContext';
import { uploadTickets } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';

export default function IncidentUploadPage() {
  const { currentProject } = useProject();
  const navigate = useNavigate();
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  if (!currentProject) {
    return (
      <div className="py-12 text-center">
        <ShieldAlert className="w-12 h-12 text-amber-500 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-slate-900">尚未選擇專案</h3>
        <p className="text-slate-500 mt-2 mb-6">請先至「專案設定」選擇或建立一個專案。</p>
        <Link to="/projects"><Button>前往專案設定</Button></Link>
      </div>
    );
  }

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
      const res = await uploadTickets(currentProject.id, file);
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
    <div className="space-y-6 max-w-4xl mx-auto">
      <Card>
        <div className="flex flex-col space-y-4">
          {error && <div className="p-3 bg-red-50 text-red-600 rounded-md text-sm">{error}</div>}
          
          <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 flex flex-col items-center justify-center bg-slate-50">
            <UploadCloud className="w-8 h-8 text-slate-400 mb-3" />
            <input 
              type="file" 
              ref={fileInputRef}
              accept=".csv,.xlsx,.json"
              onChange={handleFileChange}
              className="hidden"
              id="file-upload"
            />
            <label 
              htmlFor="file-upload" 
              className="cursor-pointer inline-flex items-center px-4 py-2 bg-white border border-slate-300 rounded-md shadow-sm text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none"
            >
              選擇檔案
            </label>
            <p className="mt-3 text-sm text-slate-500">
              {file ? file.name : '支援 CSV, Excel, JSON 格式'}
            </p>
          </div>

          <div className="flex justify-end">
            <Button 
              onClick={handleUpload} 
              disabled={!file || isUploading}
            >
              {isUploading ? '處理中...' : '開始上傳'}
            </Button>
          </div>
        </div>
      </Card>

      {result && (
        <div className="space-y-6">
          <div className="grid grid-cols-3 gap-4">
            <Card className="text-center bg-slate-50">
              <p className="text-sm text-slate-500 mb-1">原始列數</p>
              <p className="text-2xl font-semibold text-slate-800">{result.raw_count || 0}</p>
            </Card>
            <Card className="text-center bg-emerald-50 border-emerald-100">
              <p className="text-sm text-emerald-600 mb-1">清理後筆數</p>
              <p className="text-2xl font-semibold text-emerald-700">{result.cleaned_count || 0}</p>
            </Card>
            <Card className="text-center bg-red-50 border-red-100">
              <p className="text-sm text-red-600 mb-1">失敗筆數</p>
              <p className="text-2xl font-semibold text-red-700">{result.failed_count || 0}</p>
            </Card>
          </div>
          
          <div className="flex justify-end mt-8 border-t border-slate-200 pt-6">
            <Button 
              onClick={() => navigate('/analysis')}
              className="flex items-center"
              size="lg"
            >
              下一步：前往執行 AI 分析
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        </div>
      )}

    </div>
  );
}