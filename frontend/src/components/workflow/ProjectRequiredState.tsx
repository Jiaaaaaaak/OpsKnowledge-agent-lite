import { ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../ui/Button';

interface ProjectRequiredStateProps {
  // 可覆寫說明文字，預設沿用既有頁面的提示
  description?: string;
}

// 未選擇專案時的共用空狀態，沿用各頁面原本的視覺。
export function ProjectRequiredState({
  description = '請先至「專案設定」選擇或建立一個專案，才能開始此工作流程。',
}: ProjectRequiredStateProps) {
  return (
    <div className="py-12 text-center">
      <ShieldAlert className="mx-auto mb-4 h-12 w-12 text-amber-500" />
      <h3 className="text-lg font-medium text-slate-900">尚未選擇專案</h3>
      <p className="mx-auto mt-2 mb-6 max-w-md text-slate-500">{description}</p>
      <Link to="/projects">
        <Button>前往專案設定</Button>
      </Link>
    </div>
  );
}
