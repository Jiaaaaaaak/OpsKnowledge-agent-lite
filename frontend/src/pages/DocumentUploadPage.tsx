import { useState, useRef } from 'react';
import { Card } from '../components/ui/Card';
import { UploadCloud, ShieldAlert, ArrowRight, CheckCircle2 } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { useProject } from '../context/ProjectContext';
import { uploadDocument } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';

export default function DocumentUploadPage() {
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
      const res = await uploadDocument(currentProject.id, file);
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
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">上傳技術文件</h2>
        <p className="text-slate-600 mt-1">上傳 PDF 格式的技術文件，系統將自動進行切塊與向量化，作為「智能問答」的知識庫來源。</p>
      </div>

      <Card>
        <div className="flex flex-col space-y-4">
          {error && <div className="p-3 bg-red-50 text-red-600 rounded-md text-sm">{error}</div>}
          
          <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 flex flex-col items-center justify-center bg-slate-50">
            <UploadCloud className="w-8 h-8 text-slate-400 mb-3" />
            <input 
              type="file" 
              ref={fileInputRef}
              accept=".pdf"
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
              {file ? file.name : '支援 PDF 格式'}
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
          <Card className="bg-emerald-50 border-emerald-100 flex flex-col items-center py-8">
            <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center mb-4">
              <CheckCircle2 className="w-6 h-6 text-emerald-600" />
            </div>
            <h3 className="text-lg font-semibold text-emerald-900 mb-2">上傳與處理成功</h3>
            <p className="text-emerald-700 text-sm mb-6 max-w-md text-center">
              您的文件已成功切塊並存入向量資料庫，現在系統可以根據此文件回答相關問題。
            </p>
            <Button 
              onClick={() => navigate('/chat')}
              className="flex items-center bg-emerald-600 hover:bg-emerald-700 text-white"
              size="lg"
            >
              前往智能問答
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </Card>
        </div>
      )}

    </div>
  );
}