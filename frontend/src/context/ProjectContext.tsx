import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface Project {
  id: string;
  name: string;
  description?: string;
  created_at: string;
}

interface ProjectContextType {
  currentProject: Project | null;
  setCurrentProject: (project: Project | null) => void;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [currentProject, setCurrentProject] = useState<Project | null>(() => {
    const saved = localStorage.getItem('opsknowledge_project');
    return saved ? JSON.parse(saved) : null;
  });

  useEffect(() => {
    if (currentProject) {
      localStorage.setItem('opsknowledge_project', JSON.stringify(currentProject));
    } else {
      localStorage.removeItem('opsknowledge_project');
    }
  }, [currentProject]);

  return (
    <ProjectContext.Provider value={{ currentProject, setCurrentProject }}>
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (context === undefined) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
}
