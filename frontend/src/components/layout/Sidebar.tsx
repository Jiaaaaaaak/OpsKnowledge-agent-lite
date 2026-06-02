import { NavLink, useLocation } from 'react-router-dom';
import { Activity, BookOpen, FileText, LayoutDashboard, MessageSquare, Settings, PlaySquare, ListTree } from 'lucide-react';
import { useProject } from '../../context/ProjectContext';

const navigation = [
  { name: '專案設定', to: '/projects', icon: Settings },
  { name: '資料上傳', to: '/documents', icon: FileText },
  { name: '知識庫問答', to: '/chat', icon: MessageSquare },
  { name: '事件分析', to: '/analysis', icon: PlaySquare },
  { name: '儀表板', to: '/dashboard', icon: LayoutDashboard },
  { name: 'Agent 執行紀錄', to: '/agent-runs', icon: ListTree },
  { name: '系統狀態', to: '/status', icon: Activity },
];

export default function Sidebar() {
  const location = useLocation();
  const { currentProject } = useProject();

  return (
    <div className="w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0">
      <div className="h-16 flex items-center px-6 bg-slate-950 border-b border-slate-800 shrink-0">
        <BookOpen className="w-6 h-6 text-indigo-400 mr-3" />
        <span className="text-white font-semibold text-lg tracking-wide">OpsKnowledge</span>
      </div>
      
      <div className="flex-1 overflow-y-auto py-4">
        <div className="px-4 mb-4">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            目前專案
          </div>
          <div className="bg-slate-800 rounded px-3 py-2 border border-slate-700">
            {currentProject ? (
              <>
                <p className="text-sm font-medium text-white truncate" title={currentProject.name}>{currentProject.name}</p>
                <p className="text-xs text-slate-400 font-mono truncate mt-0.5">{currentProject.id.substring(0,8)}...</p>
              </>
            ) : (
              <p className="text-sm text-slate-400 italic">（尚未選擇）</p>
            )}
          </div>
        </div>

        <nav className="space-y-1 px-2">
          {navigation.map((item) => {
            const isActive = location.pathname.startsWith(item.to);
            return (
              <NavLink
                key={item.name}
                to={item.to}
                className={`group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  isActive 
                    ? 'bg-indigo-600/10 text-indigo-400' 
                    : 'hover:bg-slate-800 hover:text-white'
                }`}
              >
                <item.icon 
                  className={`mr-3 flex-shrink-0 h-5 w-5 transition-colors ${
                    isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300'
                  }`} 
                />
                {item.name}
              </NavLink>
            );
          })}
        </nav>
      </div>
      
      <div className="p-4 border-t border-slate-800 shrink-0">
        <div className="text-xs text-slate-500">
          OpsKnowledge Agent Lite
          <br />
          Version 0.1.0
        </div>
      </div>
    </div>
  );
}