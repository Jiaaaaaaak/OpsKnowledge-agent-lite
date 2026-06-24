import { NavLink, useLocation } from 'react-router-dom';
import { Activity, BookOpen, MessageSquare, ListTree } from 'lucide-react';
import { useProject } from '../../context/ProjectContext';

const navGroups = [
  {
    title: '主要流程',
    items: [
      { name: '知識庫問答流程', to: '/knowledge/workflow', icon: MessageSquare },
    ],
  },
  {
    title: '可觀測性',
    items: [
      { name: 'Agent 執行紀錄', to: '/agent-runs', icon: ListTree },
      { name: '系統狀態', to: '/status', icon: Activity },
    ],
  },
];

export default function Sidebar() {
  const location = useLocation();
  const { currentProject } = useProject();

  return (
    <div className="w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0">
      <div className="h-16 flex items-center px-6 bg-slate-950 border-b border-slate-800 shrink-0">
        <BookOpen className="w-6 h-6 text-indigo-400 mr-3 shrink-0" />
        <span className="text-white font-semibold text-lg tracking-wide truncate">
          OpsKnowledge
        </span>
      </div>
      
      <div className="flex-1 overflow-y-auto py-4">
        <div className="px-4 mb-6">
          {/* 專案狀態常駐於側邊欄頂端，點擊可前往專案設定 */}
          <NavLink
            to="/projects"
            className="block bg-slate-800 rounded px-3 py-2 border border-slate-700 transition-colors hover:border-indigo-500/50 hover:bg-slate-800/80"
          >
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">目前專案</p>
            {currentProject ? (
              <>
                <p className="text-sm font-medium text-white truncate" title={currentProject.name}>{currentProject.name}</p>
                <p className="text-xs text-slate-400 font-mono truncate mt-0.5">{currentProject.id.substring(0,8)}...</p>
              </>
            ) : (
              <p className="text-sm text-slate-400 italic">（尚未選擇專案）</p>
            )}
          </NavLink>
        </div>

        <nav className="space-y-6 px-2">
          {navGroups.map((group, groupIndex) => (
            <div key={groupIndex}>
              <div className="px-3 mb-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                {group.title}
              </div>
              <div className="space-y-1">
                {group.items.map((item) => {
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
                        className={`mr-3 flex-shrink-0 h-4 w-4 transition-colors ${
                          isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300'
                        }`} 
                      />
                      {item.name}
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>
      
      <div className="p-4 border-t border-slate-800 shrink-0">
        <div className="text-xs text-slate-500">
          Agent Lite
          <br />
          Version 0.1.0
        </div>
      </div>
    </div>
  );
}