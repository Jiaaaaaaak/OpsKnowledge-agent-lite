import { useState, useEffect } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { listProjects, createProject } from '../services/api';
import { useProject } from '../context/ProjectContext';
import { FolderGit2, Plus, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function ProjectPage() {
  const { currentProject, setCurrentProject } = useProject();
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const data = await listProjects();
      setProjects(data as any[]);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      setIsCreating(true);
      setError(null);
      const created = await createProject(newName.trim(), newDesc.trim() || undefined);
      setProjects([...projects, created]);
      setCurrentProject(created as any);
      setNewName('');
      setNewDesc('');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card title="選擇既有專案" description="選擇一個專案以進行後續操作">
        {loading ? (
          <p className="text-slate-500 text-sm py-4">載入中...</p>
        ) : projects.length === 0 ? (
          <div className="py-8 flex flex-col items-center justify-center border-2 border-dashed border-slate-200 rounded-lg">
            <FolderGit2 className="w-8 h-8 text-slate-300 mb-2" />
            <p className="text-sm text-slate-500">尚無專案 — 請在右側建立第一個。</p>
          </div>
        ) : (
          <div className="space-y-3">
            {projects.map(p => (
              <div 
                key={p.id} 
                className={`p-4 border rounded-lg flex flex-col justify-center transition-colors ${
                  currentProject?.id === p.id 
                    ? 'border-indigo-500 bg-indigo-50/50' 
                    : 'border-slate-200 hover:border-indigo-300 bg-white cursor-pointer'
                }`}
                onClick={() => currentProject?.id !== p.id && setCurrentProject(p)}
              >
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <h4 className={`font-medium ${currentProject?.id === p.id ? 'text-indigo-900' : 'text-slate-800'}`}>
                      {p.name}
                    </h4>
                    <p className="text-xs text-slate-500 mt-1 font-mono">{p.id.substring(0,8)}...</p>
                  </div>
                  {currentProject?.id !== p.id && (
                    <Button variant="outline" size="sm">選擇</Button>
                  )}
                </div>
                
                {currentProject?.id === p.id && (
                  <div className="flex justify-end mt-2 pt-2 border-t border-indigo-100">
                    <Button 
                      size="sm"
                      className="flex items-center bg-indigo-600 hover:bg-indigo-700 text-white"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate('/incident-upload');
                      }}
                    >
                      下一步：匯入事件紀錄
                      <ArrowRight className="w-4 h-4 ml-1.5" />
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="建立新專案">
        <form onSubmit={handleCreate} className="space-y-4">
          {error && <div className="p-3 bg-red-50 text-red-600 rounded-md text-sm">{error}</div>}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">名稱</label>
            <input 
              type="text" 
              required
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="例如：IT 維運示範專案"
              value={newName}
              onChange={e => setNewName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">描述（選填）</label>
            <textarea 
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 h-24 resize-none"
              value={newDesc}
              onChange={e => setNewDesc(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={!newName.trim() || isCreating} className="w-full">
            <Plus className="w-4 h-4 mr-2" />
            建立
          </Button>
        </form>
      </Card>
    </div>
  );
}