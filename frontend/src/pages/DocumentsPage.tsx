import { useState, useRef } from 'react';
import { Card } from '../components/ui/Card';
import { UploadCloud, Database, ShieldAlert } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { useProject } from '../context/ProjectContext';
import { uploadDocument, uploadTickets } from '../services/api';
import { Link } from 'react-router-dom';

export default function DocumentsPage() {
  const { currentProject } = useProject();
  const [activeTab, setActiveTab] = useState<'docs' | 'tickets'>('docs');
  
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
      let res;
      if (activeTab === 'docs') {
        res = await uploadDocument(currentProject.id, file);
      } else {
        res = await uploadTickets(currentProject.id, file);
      }
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
      <div className="flex border-b border-slate-200 mb-6">
        <button
          className={`py-3 px-6 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'docs' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
          }`}
          onClick={() => { setActiveTab('docs'); setFile(null); setResult(null); setError(null); }}
        >
          📄 技術文件 PDF
        </button>
        <button
          className={`py-3 px-6 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'tickets' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
          }`}
          onClick={() => { setActiveTab('tickets'); setFile(null); setResult(null); setError(null); }}
        >
          🎫 事件紀錄檔 (CSV/JSON)
        </button>
      </div>

      <Card 
        title={activeTab === 'docs' ? '上傳技術文件' : '上傳事件紀錄'} 
        description={activeTab === 'docs' 
          ? 'PDF 會被切 chunk → embed → 存入 ChromaDB，作為「知識庫問答」的 RAG 來源。' 
          : 'CSV / Excel / JSON 經 ETL 正規化欄位，寫入關聯資料庫，後續供「事件分析」使用。'}
      >
        <div className="flex flex-col space-y-4">
          {error && <div className="p-3 bg-red-50 text-red-600 rounded-md text-sm">{error}</div>}
          
          <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 flex flex-col items-center justify-center bg-slate-50">
            <UploadCloud className="w-8 h-8 text-slate-400 mb-3" />
            <input 
              type="file" 
              ref={fileInputRef}
              accept={activeTab === 'docs' ? ".pdf" : ".csv,.xlsx,.json"}
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
              {file ? file.name : (activeTab === 'docs' ? '支援 PDF 格式' : '支援 CSV, Excel, JSON 格式')}
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

      {result && activeTab === 'tickets' && (
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
      )}

      {result && activeTab === 'docs' && (
        <Card className="bg-emerald-50 border-emerald-100">
          <div className="flex items-center text-emerald-800 font-medium">
            <Database className="w-5 h-5 mr-2" />
            PDF 已成功上傳並建立向量索引
          </div>
          <pre className="mt-4 p-4 bg-emerald-900 text-emerald-50 rounded-md overflow-x-auto text-xs">
            {JSON.stringify(result, null, 2)}
          </pre>
        </Card>
      )}

    </div>
  );
}